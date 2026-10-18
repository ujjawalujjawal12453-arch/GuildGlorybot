import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
id_clan = 3034881538
json_data = '''
{{
    "1": {},
    "2": 1
}}
'''.format(id_clan)
data_dict = json.loads(json_data)
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\ndata.proto\"(\n\x06MyData\x12\x0e\n\x06\x66ield1\x18\x01 \x01(\r\x12\x0e\n\x06\x66ield2\x18\x02 \x01(\rb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'data_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _globals['_MYDATA']._serialized_start = 14
    _globals['_MYDATA']._serialized_end = 54
MyData = _sym_db.GetSymbol('MyData')
my_data = MyData()
my_data.field1 = data_dict["1"]
my_data.field2 = data_dict["2"]
data_bytes = my_data.SerializeToString()
padded_data = pad(data_bytes, AES.block_size)
cipher = AES.new(key, AES.MODE_CBC, iv)
encrypted_data = cipher.encrypt(padded_data)
formatted_encrypted_data = ' '.join([f"{byte:02X}" for byte in encrypted_data])
print("Encrypted data in the desired format:")
print(formatted_encrypted_data)