# Copyright 2015 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

"""Adapter between config service client and the rest of auth_service.

Basically a cron job that each minute refetches config files from config service
and modifies auth service datastore state if anything changed.

Following files are fetched:
  imports.cfg - configuration for group importer cron job.
  ip_whitelist.cfg - IP whitelists.
  oauth.cfg - OAuth client_id whitelist.

Configs are ASCII serialized protocol buffer messages. The schema is defined in
proto/config.proto.

Storing infrequently changing configuration in the config service (implemented
on top of source control) allows to use code review workflow for configuration
changes as well as removes a need to write some UI for them.
"""

import collections
import logging
import posixpath

from google import protobuf
from google.appengine.ext import ndb

from components import config
from components import datastore_utils
from components import gitiles
from components import utils
from components.auth import ipaddr
from components.auth import model
from components.config import validation

from proto import config_pb2
import importer


# Config file revision number and where it came from.
Revision = collections.namedtuple('Revision', ['revision', 'url'])


class CannotLoadConfigError(Exception):
  """Raised when fetching configs if they are missing or invalid."""


def is_remote_configured():
  """True if config service backend URL is defined.

  If config service backend URL is not set auth_service will use datastore
  as source of truth for configuration (with some simple web UI to change it).

  If config service backend URL is set, UI for config management will be read
  only and all config changes must be performed through the config service.
  """
  return bool(get_remote_url())


def get_remote_url():
  """Returns URL of a config service if configured, to display in UI."""
  settings = config.ConfigSettings.cached()
  if settings and settings.service_hostname:
    return 'https://%s' % settings.service_hostname
  return None


def get_revisions():
  """Returns a mapping {config file name => Revision instance or None}."""
  return dict(utils.async_apply(_CONFIG_SCHEMAS, _get_config_revision_async))


def _get_config_revision_async(path):
  """Returns tuple with info about last imported config revision."""
  assert path in _CONFIG_SCHEMAS, path
  schema = _CONFIG_SCHEMAS.get(path)
  return schema['revision_getter']()


@utils.cache_with_expiration(expiration_sec=60)
def get_settings():
  """Returns auth service own settings (from settings.cfg) as SettingsCfg proto.

  Returns default settings if the ones in the datastore are no longer valid.
  """
  text = _get_service_config('settings.cfg')
  if not text:
    return config_pb2.SettingsCfg()
  # The config MUST be valid, since we do validation before storing it. If it
  # doesn't, better to revert to default setting rather than fail all requests.
  try:
    msg = config_pb2.SettingsCfg()
    protobuf.text_format.Merge(text, msg)
    return msg
  except protobuf.text_format.ParseError as ex:
    logging.error('Invalid settings.cfg: %s', ex)
    return config_pb2.SettingsCfg()


def refetch_config(force=False):
  """Refetches all configs from luci-config (if enabled).

  Called as a cron job.
  """
  if not is_remote_configured():
    logging.info('Config remote is not configured')
    return

  # Grab and validate all new configs in parallel.
  try:
    configs = _fetch_configs(_CONFIG_SCHEMAS)
  except CannotLoadConfigError as exc:
    logging.error('Failed to fetch configs\n%s', exc)
    return

  # Figure out what needs to be updated.
  dirty = {}
  dirty_in_authdb = {}

  cur_revs = dict(utils.async_apply(configs, _get_config_revision_async))
  for path, (new_rev, conf) in sorted(configs.iteritems()):
    assert path in _CONFIG_SCHEMAS, path
    cur_rev = cur_revs[path]
    if cur_rev != new_rev or force:
      if _CONFIG_SCHEMAS[path]['use_authdb_transaction']:
        dirty_in_authdb[path] = (new_rev, conf)
      else:
        dirty[path] = (new_rev, conf)
    else:
      logging.info('Config %s is up-to-date at rev %s', path, cur_rev.revision)

  # First update configs that do not touch AuthDB, one by one.
  for path, (rev, conf) in sorted(dirty.iteritems()):
    dirty = _CONFIG_SCHEMAS[path]['updater'](rev, conf)
    logging.info(
        'Processed %s at rev %s: %s', path, rev.revision,
        'updated' if dirty else 'up-to-date')

  # Configs that touch AuthDB are updated in a single transaction so that config
  # update generates single AuthDB replication task instead of a bunch of them.
  if dirty_in_authdb:
    _update_authdb_configs(dirty_in_authdb)


### Integration with config validation framework.


@validation.self_rule('settings.cfg', config_pb2.SettingsCfg)
def validate_settings_cfg(conf, _ctx):
  assert isinstance(conf, config_pb2.SettingsCfg)
  # Nothing to validate here actually. There's only one boolean field in
  # SettingsCfg.


# TODO(vadimsh): Below use validation context for real (e.g. emit multiple
# errors at once instead of aborting on the first one).


@validation.self_rule('imports.cfg')
def validate_imports_config(conf, ctx):
  try:
    importer.validate_config(conf)
  except ValueError as exc:
    ctx.error(str(exc))


@validation.self_rule('ip_whitelist.cfg', config_pb2.IPWhitelistConfig)
def validate_ip_whitelist_config(conf, ctx):
  try:
    _validate_ip_whitelist_config(conf)
  except ValueError as exc:
    ctx.error(str(exc))


@validation.self_rule('oauth.cfg', config_pb2.OAuthConfig)
def validate_oauth_config(conf, ctx):
  try:
    _validate_oauth_config(conf)
  except ValueError as exc:
    ctx.error(str(exc))


# Simple auth_serivce own configs stored in the datastore as plain text.
# They are different from imports.cfg (no GUI to update them other), and from
# ip_whitelist.cfg and oauth.cfg (not tied to AuthDB changes).


class _AuthServiceConfig(ndb.Model):
  """Text config file imported from luci-config.

  Root entity. Key ID is config file name.
  """
  # The body of the config itself.
  config = ndb.TextProperty()
  # Last imported SHA1 revision of the config.
  revision = ndb.StringProperty(indexed=False)
  # URL the config was imported from.
  url = ndb.StringProperty(indexed=False)


@ndb.tasklet
def _get_service_config_rev_async(cfg_name):
  """Returns last processed Revision of given config."""
  e = yield _AuthServiceConfig.get_by_id_async(cfg_name)
  raise ndb.Return(Revision(e.revision, e.url) if e else None)


def _get_service_config(cfg_name):
  """Returns text of given config file or None if missing."""
  e = _AuthServiceConfig.get_by_id(cfg_name)
  return e.config if e else None


@ndb.transactional
def _update_service_config(cfg_name, rev, conf):
  """Stores new config (and its revision).

  This function is called only if config has already been validated.
  """
  assert isinstance(conf, basestring)
  e = _AuthServiceConfig.get_by_id(cfg_name) or _AuthServiceConfig(id=cfg_name)
  old = e.config
  e.populate(config=conf, revision=rev.revision, url=rev.url)
  e.put()
  return old != conf


### Group importer config implementation details.


@ndb.tasklet
def _get_imports_config_revision_async():
  """Returns Revision of last processed imports.cfg config."""
  e = yield importer.config_key().get_async()
  if not e or not isinstance(e.config_revision, dict):
    raise ndb.Return(None)
  desc = e.config_revision
  raise ndb.Return(Revision(desc.get('rev'), desc.get('url')))


def _update_imports_config(rev, conf):
  """Applies imports.cfg config."""
  # Rewrite existing config even if it is the same (to update 'rev').
  cur = importer.read_config()
  importer.write_config(conf, {'rev': rev.revision, 'url': rev.url})
  return cur != conf


### Implementation of configs expanded to AuthDB entities.


class _ImportedConfigRevisions(ndb.Model):
  """Stores mapping config path -> {'rev': SHA1, 'url': URL}.

  Parent entity is AuthDB root (auth.model.root_key()). Updated in a transaction
  when importing configs.
  """
  revisions = ndb.JsonProperty()


def _imported_config_revisions_key():
  return ndb.Key(_ImportedConfigRevisions, 'self', parent=model.root_key())


@ndb.tasklet
def _get_authdb_config_rev_async(path):
  """Returns Revision of last processed config given its name."""
  mapping = yield _imported_config_revisions_key().get_async()
  if not mapping or not isinstance(mapping.revisions, dict):
    raise ndb.Return(None)
  desc = mapping.revisions.get(path)
  if not isinstance(desc, dict):
    raise ndb.Return(None)
  raise ndb.Return(Revision(desc.get('rev'), desc.get('url')))


@datastore_utils.transactional
def _update_authdb_configs(configs):
  """Pushes new configs to AuthDB entity group.

  Args:
    configs: dict {config path -> (Revision tuple, <config>)}.
  """
  revs = _imported_config_revisions_key().get()
  if not revs:
    revs = _ImportedConfigRevisions(
        key=_imported_config_revisions_key(),
        revisions={})
  some_dirty = False
  for path, (rev, conf) in sorted(configs.iteritems()):
    dirty = _CONFIG_SCHEMAS[path]['updater'](rev, conf)
    revs.revisions[path] = {'rev': rev.revision, 'url': rev.url}
    logging.info(
        'Processed %s at rev %s: %s', path, rev.revision,
        'updated' if dirty else 'up-to-date')
    some_dirty = some_dirty or dirty
  revs.put()
  if some_dirty:
    model.replicate_auth_db()


def _validate_ip_whitelist_config(conf):
  if not isinstance(conf, config_pb2.IPWhitelistConfig):
    raise ValueError('Wrong message type: %s' % conf.__class__.__name__)
  whitelists = set()
  for ip_whitelist in conf.ip_whitelists:
    if not model.IP_WHITELIST_NAME_RE.match(ip_whitelist.name):
      raise ValueError('Invalid IP whitelist name: %s' % ip_whitelist.name)
    if ip_whitelist.name in whitelists:
      raise ValueError('IP whitelist %s is defined twice' % ip_whitelist.name)
    whitelists.add(ip_whitelist.name)
    for net in ip_whitelist.subnets:
      # Raises ValueError if subnet is not valid.
      ipaddr.subnet_from_string(net)
  idents = []
  for assignment in conf.assignments:
    # Raises ValueError if identity is not valid.
    ident = model.Identity.from_bytes(assignment.identity)
    if assignment.ip_whitelist_name not in whitelists:
      raise ValueError(
          'Unknown IP whitelist: %s' % assignment.ip_whitelist_name)
    if ident in idents:
      raise ValueError('Identity %s is specified twice' % assignment.identity)
    idents.append(ident)
  # This raises ValueError on bad includes.
  _resolve_ip_whitelist_includes(conf.ip_whitelists)


def _resolve_ip_whitelist_includes(whitelists):
  """Takes a list of IPWhitelist, returns map {name -> [subnets]}.

  Subnets are returned as sorted list of strings.
  """
  by_name = {m.name: m for m in whitelists}

  def resolve_one(wl, visiting):
    if wl.name in visiting:
      raise ValueError(
          'IP whitelist %s is part of an include cycle %s' %
          (wl.name, visiting + [wl.name]))
    visiting.append(wl.name)
    subnets = set(wl.subnets)
    for inc in wl.includes:
      if inc not in by_name:
        raise ValueError(
            'IP whitelist %s includes unknown whitelist %s' % (wl.name, inc))
      subnets |= resolve_one(by_name[inc], visiting)
    visiting.pop()
    return subnets

  return {m.name: sorted(resolve_one(m, [])) for m in whitelists}


def _update_ip_whitelist_config(rev, conf):
  assert ndb.in_transaction(), 'Must be called in AuthDB transaction'
  now = utils.utcnow()

  # Existing whitelist entities.
  existing_ip_whitelists = {
    e.key.id(): e
    for e in model.AuthIPWhitelist.query(ancestor=model.root_key())
  }

  # Whitelists being imported (name => [list of subnets]).
  imported_ip_whitelists = _resolve_ip_whitelist_includes(conf.ip_whitelists)

  to_put = []
  to_delete = []

  # New or modified IP whitelists.
  for name, subnets in imported_ip_whitelists.iteritems():
    # An existing whitelist and it hasn't changed?
    wl = existing_ip_whitelists.get(name)
    if wl and wl.subnets == subnets:
      continue
    # Update the existing (to preserve auth_db_prev_rev) or create a new one.
    if not wl:
      wl = model.AuthIPWhitelist(
          key=model.ip_whitelist_key(name),
          created_ts=now,
          created_by=model.get_service_self_identity())
    wl.subnets = subnets
    wl.description = 'Imported from ip_whitelist.cfg'
    to_put.append(wl)

  # Removed IP whitelists.
  for wl in existing_ip_whitelists.itervalues():
    if wl.key.id() not in imported_ip_whitelists:
      to_delete.append(wl)

  # Update assignments. Don't touch created_ts and created_by for existing ones.
  ip_whitelist_assignments = (
      model.ip_whitelist_assignments_key().get() or
      model.AuthIPWhitelistAssignments(
          key=model.ip_whitelist_assignments_key()))
  existing = {
    (a.identity.to_bytes(), a.ip_whitelist): a
    for a in ip_whitelist_assignments.assignments
  }
  updated = []
  for a in conf.assignments:
    key = (a.identity, a.ip_whitelist_name)
    if key in existing:
      updated.append(existing[key])
    else:
      new_one = model.AuthIPWhitelistAssignments.Assignment(
          identity=model.Identity.from_bytes(a.identity),
          ip_whitelist=a.ip_whitelist_name,
          comment='Imported from ip_whitelist.cfg at rev %s' % rev.revision,
          created_ts=now,
          created_by=model.get_service_self_identity())
      updated.append(new_one)

  # Something has changed?
  updated_keys = [
    (a.identity.to_bytes(), a.ip_whitelist)
    for a in updated
  ]
  if set(updated_keys) != set(existing):
    ip_whitelist_assignments.assignments = updated
    to_put.append(ip_whitelist_assignments)

  if not to_put and not to_delete:
    return False
  comment = 'Importing ip_whitelist.cfg at rev %s' % rev.revision
  for e in to_put:
    e.record_revision(
        modified_by=model.get_service_self_identity(),
        modified_ts=now,
        comment=comment)
  for e in to_delete:
    e.record_deletion(
        modified_by=model.get_service_self_identity(),
        modified_ts=now,
        comment=comment)
  futures = []
  futures.extend(ndb.put_multi_async(to_put))
  futures.extend(ndb.delete_multi_async(e.key for e in to_delete))
  for f in futures:
    f.check_success()
  return True


def _validate_oauth_config(conf):
  if not isinstance(conf, config_pb2.OAuthConfig):
    raise ValueError('Wrong message type')
  if conf.token_server_url:
    utils.validate_root_service_url(conf.token_server_url)


def _update_oauth_config(rev, conf):
  assert ndb.in_transaction(), 'Must be called in AuthDB transaction'
  existing = model.root_key().get()
  existing_as_dict = {
    'oauth_client_id': existing.oauth_client_id,
    'oauth_client_secret': existing.oauth_client_secret,
    'oauth_additional_client_ids': list(existing.oauth_additional_client_ids),
    'token_server_url': existing.token_server_url,
  }
  new_as_dict = {
    'oauth_client_id': conf.primary_client_id,
    'oauth_client_secret': conf.primary_client_secret,
    'oauth_additional_client_ids': list(conf.client_ids),
    'token_server_url': conf.token_server_url,
  }
  if new_as_dict == existing_as_dict:
    return False
  existing.populate(**new_as_dict)
  existing.record_revision(
      modified_by=model.get_service_self_identity(),
      modified_ts=utils.utcnow(),
      comment='Importing oauth.cfg at rev %s' % rev.revision)
  existing.put()
  return True


### Description of all known config files: how to validate and import them.

# Config file name -> {
#   'proto_class': protobuf class of the config or None to keep it as text,
#   'revision_getter': lambda: ndb.Future with <latest imported Revision>
#   'validator': lambda config: <raises ValueError on invalid format>
#   'updater': lambda rev, config: True if applied, False if not.
#   'use_authdb_transaction': True to call 'updater' in AuthDB transaction.
#   'default': Default config value to use if the config file is missing.
# }
_CONFIG_SCHEMAS = {
  'imports.cfg': {
    'proto_class': None, # importer configs are stored as text
    'revision_getter': _get_imports_config_revision_async,
    'updater': _update_imports_config,
    'use_authdb_transaction': False,
  },
  'ip_whitelist.cfg': {
    'proto_class': config_pb2.IPWhitelistConfig,
    'revision_getter': lambda: _get_authdb_config_rev_async('ip_whitelist.cfg'),
    'updater': _update_ip_whitelist_config,
    'use_authdb_transaction': True,
  },
  'oauth.cfg': {
    'proto_class': config_pb2.OAuthConfig,
    'revision_getter': lambda: _get_authdb_config_rev_async('oauth.cfg'),
    'updater': _update_oauth_config,
    'use_authdb_transaction': True,
  },
  'settings.cfg': {
    'proto_class': None, # settings are stored as text in datastore
    'default': '',  # it's fine if config file is not there
    'revision_getter': lambda: _get_service_config_rev_async('settings.cfg'),
    'updater': lambda rev, c: _update_service_config('settings.cfg', rev, c),
    'use_authdb_transaction': False,
  },
}


@utils.memcache('auth_service:get_configs_url', time=300)
def _get_configs_url():
  """Returns URL where luci-config fetches configs from."""
  url = config.get_config_set_location(config.self_config_set())
  return url or 'about:blank'


def _fetch_configs(paths):
  """Fetches a bunch of config files in parallel and validates them.

  Returns:
    dict {path -> (Revision tuple, <config>)}.

  Raises:
    CannotLoadConfigError if some config is missing or invalid.
  """
  paths = sorted(paths)
  configs_url = _get_configs_url()
  out = {}
  configs = utils.async_apply(
      paths,
      lambda p: config.get_self_config_async(
          p, dest_type=_CONFIG_SCHEMAS[p]['proto_class'], store_last_good=False)
  )
  for path, (rev, conf) in configs:
    if conf is None:
      default = _CONFIG_SCHEMAS[path].get('default')
      if default is None:
        raise CannotLoadConfigError('Config %s is missing' % path)
      rev, conf = '0'*40, default
    try:
      validation.validate(config.self_config_set(), path, conf)
    except ValueError as exc:
      raise CannotLoadConfigError(
          'Config %s at rev %s failed to pass validation: %s' %
          (path, rev, exc))
    out[path] = (Revision(rev, _gitiles_url(configs_url, rev, path)), conf)
  return out


def _gitiles_url(configs_url, rev, path):
  """URL to a directory in gitiles -> URL to a file at concrete revision."""
  try:
    location = gitiles.Location.parse(configs_url)
    return str(gitiles.Location(
        hostname=location.hostname,
        project=location.project,
        treeish=rev,
        path=posixpath.join(location.path, path)))
  except ValueError:
    # Not a gitiles URL, return as is.
    return configs_url
