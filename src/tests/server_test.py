#!/usr/bin/python2.7
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Drives test on the Swarm server with a test machine provider."""




import cookielib
import httplib
import json
import logging
import optparse
import os
import subprocess
import sys
import time
import unittest
import urllib
import urllib2
import urlparse


# Number of seconds to sleep between tries of polling for results.
SLEEP_BETWEEN_RESULT_POLLS = 2

ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


# TODO(user): Find a way to avoid spawning other processes so that we can
# get code coverage, which doesn't work for code in other processes in Python.
class _ProcessWrapper(object):
  """This class controls the life span of a child process.

  Attributes:
    command_line: An array with the command to execute followed by its args.
  """

  def __init__(self, command_line):
    self.wrapped_process = subprocess.Popen(command_line)

  def __del__(self):
    if hasattr(self, 'wrapped_process') and self.wrapped_process.poll() is None:
      self.wrapped_process.terminate()


class _SwarmTestCase(unittest.TestCase):
  """Test case class for Swarm integration tests."""

  def GetAdminUrl(self, url=None):
    """"Returns an url to login an admin user and then go to a url (if given).

    Args:
      url: The url to continue to.

    Returns:
      The full url.
    """
    admin_url = urlparse.urljoin(self._swarm_server_url, '_ah/login?'
                                 'email=john@doe.com&admin=True&action=Login')

    if url:
      admin_url += '&continue=' + urllib2.quote(url)

    return admin_url

  def setUp(self):
    self._swarm_server_process = None
    self._slave_machine_process = None

    swarm_server_addr = 'http://localhost'
    swarm_server_port = '8181'
    self._swarm_server_url = '%s:%s' % (swarm_server_addr, swarm_server_port)

    _SwarmTestProgram.options.appengine_cmds.extend(
        ['-c', '-p %s' % swarm_server_port, '--skip_sdk_update_check',
         _SwarmTestProgram.options.swarm_path])

    self._swarm_server_process = _ProcessWrapper(
        _SwarmTestProgram.options.appengine_cmds)
    logging.info('Started Swarm server Process with pid: %s',
                 self._swarm_server_process.wrapped_process.pid)

    # Wait for the Swarm server to be ready
    ready = False
    time_out = _SwarmTestProgram.options.swarm_server_start_timeout
    started = time.time()
    while not ready and time_out > time.time() - started:
      try:
        urllib2.urlopen(self._swarm_server_url)
        ready = True
      except urllib2.URLError:
        time.sleep(1)
    self.assertTrue(ready, 'The swarm server could not be started')

    # Whitelist the machine to be allowed to run tests.
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    opener.open(self.GetAdminUrl())

    opener.open(urlparse.urljoin(self._swarm_server_url,
                                 'secure/change_whitelist'),
                urllib.urlencode({'a': True}))

    # Start the slave machine script to start polling for tests.
    logging.info('Current dir: %s', os.getcwd())
    logging.info('Trying to run slave script: %s',
                 _SwarmTestProgram.options.slave_script)

    slave_machine_cmds = [
        sys.executable,
        _SwarmTestProgram.options.slave_script,
        '-a', swarm_server_addr,
        '-p', swarm_server_port,
        '-d', '/tmp',
        '-l', '/tmp/slave.log',
        _SwarmTestProgram.options.slave_config_file
        ]

    if _SwarmTestProgram.options.verbose:
      slave_machine_cmds.append('-v')
    self._slave_machine_process = _ProcessWrapper(slave_machine_cmds)
    logging.info('Started slave machine process with pid: %s',
                 self._slave_machine_process.wrapped_process.pid)

  def tearDown(self):
    try:
      logging.info('Quitting Swarm server')
      cj = cookielib.CookieJar()
      opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
      opener.open(self.GetAdminUrl(urlparse.urljoin(self._swarm_server_url,
                                                    'tasks/quitquitquit')))
      # TODO(user): This line shouldn't be here, should be after the
      # try block.
      self._swarm_server_process.wrapped_process.wait()
    except (httplib.BadStatusLine, urllib2.HTTPError):
      # We expect this to throw since the quitquitquit request caused the
      # server to terminate and thus it won't be able to complete the request.
      pass

  def testHandlingSwarmFiles(self):
    """This test sends a series of Swarm files to the server."""
    swarm_files = []
    logging.info('Walking %s, looking for Swarm files.',
                 os.path.join(os.environ['TEST_SRCDIR'],
                              _SwarmTestProgram.options.tests_path))
    for dirpath, _, filenames in os.walk(os.path.join(
        os.environ['TEST_SRCDIR'], _SwarmTestProgram.options.tests_path)):
      for filename in filenames:
        if os.path.splitext(filename)[1].lower() == '.swarm':
          swarm_files.append(os.path.join(dirpath, filename))

    self.assertTrue(swarm_files, 'No swarm files found to test, considering '
                    'this a failure since the end-to-end process won\'t be '
                    'tested')

    logging.info('Will send these files to Swarm server: %s', swarm_files)

    swarm_server_test_url = urlparse.urljoin(self._swarm_server_url, 'test')
    running_test_keys = []
    for swarm_file in swarm_files:
      logging.info('Sending content of %s to Swarm server.', swarm_file)
      # Build the URL for sending the request.
      test_request = open(swarm_file)
      output = None
      try:
        output = urllib2.urlopen(swarm_server_test_url,
                                 data=test_request.read()).read()
      except urllib2.URLError as ex:
        self.fail('Error: %s' % str(ex))

      # Check that we can read the output as a JSON string
      try:
        test_keys = json.loads(output)
      except (ValueError, TypeError) as e:
        self.fail('Swarm Request failed: %s' % output)

      logging.info(test_keys)

      for test_key in test_keys['test_keys']:
        running_test_keys.append(test_key)
        if _SwarmTestProgram.options.verbose:
          logging.info('Config: %s, index: %s/%s, test key: %s',
                       test_key['config_name'],
                       int(test_key['instance_index']) + 1,
                       test_key['num_instances'],
                       test_key['test_key'])

    # TODO(user): This code below and a big chunk of the parts above were stolen
    # from the post_test.py script under the tools folder. We should find a
    # way to extract and reuse it somehow.
    test_result_output = ''
    # TODO(user): Maybe collect all failures so that we can enumerate them at
    # the end as the local test runner and gtest does.

    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    urllib2.install_opener(opener)

    # The slave machine is running along with this test. Thus it may take
    # some time before all the tests complete. We will keep polling the results
    # with delays between them. If after 10 times all the tests are still not
    # completed, we report a failure..
    for _ in range(10):
      test_all_succeeded = True
      for running_test_key in running_test_keys:
        key_url = self.GetAdminUrl(
            urlparse.urljoin(
                self._swarm_server_url,
                'secure/get_result?r=' + running_test_key['test_key']))

        logging.info('Opening URL %s', key_url)
        try:
          output = urllib2.urlopen(key_url).read()
        except urllib2.HTTPError as e:
          self.fail('Calling %s threw %s' % (key_url, e))

        assert output
        if _SwarmTestProgram.options.verbose:
          test_result_output = (
              '%s\n=======================\nConfig: %s\n%s' %
              (test_result_output, running_test_key['config_name'], output))
        if test_all_succeeded and '0 FAILED TESTS' not in output:
          test_all_succeeded = False
        if _SwarmTestProgram.options.verbose:
          logging.info('Test done for %s', running_test_key['config_name'])
      if _SwarmTestProgram.options.verbose:
        logging.info(test_result_output)
        logging.info('=======================')
      if test_all_succeeded:
        logging.info('All tests succeeded')
        break
      else:
        logging.info('At least one test not yet succeeded')

      time.sleep(SLEEP_BETWEEN_RESULT_POLLS)

    if not test_all_succeeded:
      self.fail('At least one test failed')


class _SwarmTestProgram(unittest.TestProgram):
  """The Swarm specific test program so that we can have specialised options."""

  # Command line options
  options = None

  # TODO(user): Find a way to also display base class command line args for -h.
  _DESCRIPTION = ('This script starts a Swarm server with a test machine '
                  'provider and runs a server mocking provided machines.')

  def parseArgs(self, argv):
    """Overloaded from base class so we can add our own options."""
    parser = optparse.OptionParser(usage='%prog [options] [filename]',
                                   description=_SwarmTestProgram._DESCRIPTION)
    parser.add_option('-a', '--appengine', dest='appengine_cmds',
                      action='append', help='The command(s) to start the '
                      'AppEngine launcher. The -c, -p, and '
                      '--skip_sdk_update_check arguments will '
                      'be added to the command(s) you specify.')
    parser.add_option('-s', '--swarm', dest='swarm_path',
                      default=ROOT_DIR,
                      help='The root path of the Swarm server code.')
    parser.add_option('-t', '--tests', dest='tests_path',
                      default=os.path.join(ROOT_DIR, 'tests/test_files'),
                      help='The path where the test files can be found.')
    parser.add_option('-c', '--slave-config', dest='slave_config_file',
                      default=os.path.join(ROOT_DIR, 'tests',
                                           'machine_config.txt'),
                      help='The path to the slave dimensions config file. '
                      'Defaults to %default.')
    parser.add_option('-l', '--slave-script', dest='slave_script',
                      default=os.path.join(ROOT_DIR, 'test_runner',
                                           'slave_machine.py'),
                      help='The path to the slave_machine.py script. '
                      'Defaults to %default.')
    parser.add_option('-o', '--swarm_server_start_timeout',
                      dest='swarm_server_start_timeout', type=int,
                      default=90,
                      help='How long should we wait (in seconds) for the '
                      'Swarm server to start? Defaults to %default seconds.')
    parser.add_option('-v', '--verbose', action='store_true',
                      help='Set logging level to INFO. Optional. Defaults to '
                      'ERROR level.')

    (_SwarmTestProgram.options, other_args) = parser.parse_args(args=argv[1:])
    if not _SwarmTestProgram.options.appengine_cmds:
      parser.error('You must specify the AppEngine command(s) to start the '
                   'AppEngine launcher.')

    if _SwarmTestProgram.options.verbose:
      logging.getLogger().setLevel(logging.INFO)
    else:
      logging.getLogger().setLevel(logging.ERROR)

    test_srcdir = os.environ['TEST_SRCDIR']
    if test_srcdir:
      _SwarmTestProgram.options.appengine_cmds[0] = os.path.join(
          test_srcdir, _SwarmTestProgram.options.appengine_cmds[0])
      _SwarmTestProgram.options.swarm_path = os.path.join(
          test_srcdir, _SwarmTestProgram.options.swarm_path)
      _SwarmTestProgram.options.slave_script = os.path.join(
          test_srcdir, _SwarmTestProgram.options.slave_script)
      _SwarmTestProgram.options.slave_config_file = os.path.join(
          test_srcdir, _SwarmTestProgram.options.slave_config_file)
    super(_SwarmTestProgram, self).parseArgs(other_args)


if __name__ == '__main__':
  if 'TEST_SRCDIR' not in os.environ:
    os.environ['TEST_SRCDIR'] = ''
  _SwarmTestProgram()
