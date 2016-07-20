# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: delegation.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)




DESCRIPTOR = _descriptor.FileDescriptor(
  name='delegation.proto',
  package='components.auth.proto.delegation',
  serialized_pb='\n\x10\x64\x65legation.proto\x12 components.auth.proto.delegation\"x\n\x0f\x44\x65legationToken\x12 \n\x18serialized_subtoken_list\x18\x01 \x01(\x0c\x12\x11\n\tsigner_id\x18\x02 \x01(\t\x12\x16\n\x0esigning_key_id\x18\x03 \x01(\t\x12\x18\n\x10pkcs1_sha256_sig\x18\x04 \x01(\x0c\"M\n\x0cSubtokenList\x12=\n\tsubtokens\x18\x01 \x03(\x0b\x32*.components.auth.proto.delegation.Subtoken\"\xa1\x01\n\x08Subtoken\x12\x11\n\tissuer_id\x18\x01 \x01(\t\x12\x15\n\rcreation_time\x18\x02 \x01(\x03\x12\x19\n\x11validity_duration\x18\x03 \x01(\x05\x12\x13\n\x0bsubtoken_id\x18\x04 \x01(\x03\x12\x10\n\x08\x61udience\x18\x05 \x03(\t\x12\x10\n\x08services\x18\x06 \x03(\t\x12\x17\n\x0fimpersonator_id\x18\x07 \x01(\t')




_DELEGATIONTOKEN = _descriptor.Descriptor(
  name='DelegationToken',
  full_name='components.auth.proto.delegation.DelegationToken',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='serialized_subtoken_list', full_name='components.auth.proto.delegation.DelegationToken.serialized_subtoken_list', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='signer_id', full_name='components.auth.proto.delegation.DelegationToken.signer_id', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='signing_key_id', full_name='components.auth.proto.delegation.DelegationToken.signing_key_id', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='pkcs1_sha256_sig', full_name='components.auth.proto.delegation.DelegationToken.pkcs1_sha256_sig', index=3,
      number=4, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=54,
  serialized_end=174,
)


_SUBTOKENLIST = _descriptor.Descriptor(
  name='SubtokenList',
  full_name='components.auth.proto.delegation.SubtokenList',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='subtokens', full_name='components.auth.proto.delegation.SubtokenList.subtokens', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=176,
  serialized_end=253,
)


_SUBTOKEN = _descriptor.Descriptor(
  name='Subtoken',
  full_name='components.auth.proto.delegation.Subtoken',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='issuer_id', full_name='components.auth.proto.delegation.Subtoken.issuer_id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='creation_time', full_name='components.auth.proto.delegation.Subtoken.creation_time', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='validity_duration', full_name='components.auth.proto.delegation.Subtoken.validity_duration', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='subtoken_id', full_name='components.auth.proto.delegation.Subtoken.subtoken_id', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='audience', full_name='components.auth.proto.delegation.Subtoken.audience', index=4,
      number=5, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='services', full_name='components.auth.proto.delegation.Subtoken.services', index=5,
      number=6, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='impersonator_id', full_name='components.auth.proto.delegation.Subtoken.impersonator_id', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=256,
  serialized_end=417,
)

_SUBTOKENLIST.fields_by_name['subtokens'].message_type = _SUBTOKEN
DESCRIPTOR.message_types_by_name['DelegationToken'] = _DELEGATIONTOKEN
DESCRIPTOR.message_types_by_name['SubtokenList'] = _SUBTOKENLIST
DESCRIPTOR.message_types_by_name['Subtoken'] = _SUBTOKEN

class DelegationToken(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DELEGATIONTOKEN

  # @@protoc_insertion_point(class_scope:components.auth.proto.delegation.DelegationToken)

class SubtokenList(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SUBTOKENLIST

  # @@protoc_insertion_point(class_scope:components.auth.proto.delegation.SubtokenList)

class Subtoken(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SUBTOKEN

  # @@protoc_insertion_point(class_scope:components.auth.proto.delegation.Subtoken)


# @@protoc_insertion_point(module_scope)
