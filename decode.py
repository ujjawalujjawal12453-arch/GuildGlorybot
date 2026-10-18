import re
import json
import binascii


HEX_DATA = """
08d5a4adaf0b121fd2a8e1b49ce1b487e1b487eaa4aaeaa4a8eaa4aaeaa4aaeaa4a8eaa4aa4e2e188ab3bcd10620fae8d4b81528043023381f4801620857656c636f6d65216a03494e44720e7b2274616773223a205b31345d7d7a025b5da001dfd403b801ba95d2b80988020da002fcf401a802b236b00204b80292af0cc802e907e002b5a7b2d506e80201fa02008a0300
"""


def decode_varint(data, pos):
    """Decode a Protocol Buffers-style varint."""
    value = 0
    shift = 0

    while pos < len(data):
        byte = data[pos]
        pos += 1

        value |= (byte & 0x7F) << shift

        if not (byte & 0x80):
            return value, pos

        shift += 7

        if shift >= 70:
            raise ValueError("Varint is too large")

    raise ValueError("Incomplete varint")


def extract_strings(data):
    """Extract printable ASCII strings from binary data."""
    text = data.decode("utf-8", errors="replace")

    strings = re.findall(r"[\x20-\x7E]{3,}", text)

    return strings


def decode_hex(hex_string):
    # Remove whitespace and validate hexadecimal characters.
    hex_string = re.sub(r"\s+", "", hex_string)

    if not hex_string:
        raise ValueError("Hex input is empty")

    if not re.fullmatch(r"[0-9a-fA-F]+", hex_string):
        raise ValueError("Input contains invalid hexadecimal characters")

    if len(hex_string) % 2:
        raise ValueError("Hex input must contain an even number of digits")

    data = bytes.fromhex(hex_string)

    print("=" * 60)
    print("HEX DECODER")
    print("=" * 60)

    print(f"\nBinary size: {len(data)} bytes")

    # 1. Hexadecimal
    print("\n[1] HEX:")
    print(data.hex())

    # 2. UTF-8 text
    print("\n[2] UTF-8 TEXT:")
    print(data.decode("utf-8", errors="replace"))

    # 3. Printable strings
    print("\n[3] EXTRACTED STRINGS:")
    strings = extract_strings(data)

    for item in strings:
        print(repr(item))

    # 4. Raw bytes
    print("\n[4] RAW BYTES:")
    print(data)

    # 5. Base64
    import base64
    print("\n[5] BASE64:")
    print(base64.b64encode(data).decode("ascii"))

    # 6. Attempt JSON parsing on extracted strings.
    print("\n[6] JSON DETECTION:")

    found_json = False

    for item in strings:
        try:
            parsed = json.loads(item)
            print(json.dumps(parsed, indent=2))
            found_json = True
        except json.JSONDecodeError:
            continue

    if not found_json:
        print("No standalone JSON string detected.")

    # 7. Attempt Protobuf wire-format parsing.
    print("\n[7] PROTOBUF-STYLE WIRE SCAN:")

    pos = 0

    try:
        while pos < len(data):
            start = pos
            key, pos = decode_varint(data, pos)

            field_number = key >> 3
            wire_type = key & 7

            if field_number == 0:
                print(f"Invalid field key at offset {start}")
                break

            if wire_type == 0:
                value, pos = decode_varint(data, pos)
                print(
                    f"offset={start}, field={field_number}, "
                    f"wire_type=0, varint={value}"
                )

            elif wire_type == 1:
                if pos + 8 > len(data):
                    raise ValueError("Incomplete 64-bit field")

                value = data[pos:pos + 8]
                pos += 8

                print(
                    f"offset={start}, field={field_number}, "
                    f"wire_type=1, hex={value.hex()}"
                )

            elif wire_type == 2:
                length, pos = decode_varint(data, pos)

                if pos + length > len(data):
                    raise ValueError("Length-delimited field exceeds data")

                value = data[pos:pos + length]
                pos += length

                print(
                    f"offset={start}, field={field_number}, "
                    f"wire_type=2, length={length}, "
                    f"hex={value.hex()}, "
                    f"text={value.decode('utf-8', errors='replace')!r}"
                )

            elif wire_type == 5:
                if pos + 4 > len(data):
                    raise ValueError("Incomplete 32-bit field")

                value = data[pos:pos + 4]
                pos += 4

                print(
                    f"offset={start}, field={field_number}, "
                    f"wire_type=5, hex={value.hex()}"
                )

            else:
                raise ValueError(f"Unsupported wire type {wire_type}")

    except ValueError as exc:
        print(f"Wire scan stopped: {exc}")
        print("The data may not be a standalone Protobuf message.")

    print("\n" + "=" * 60)
    print("DECODING FINISHED")
    print("=" * 60)


if __name__ == "__main__":
    decode_hex(HEX_DATA)