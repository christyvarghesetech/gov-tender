import zipfile
import re

import zipfile
import re

def parse_class_strings(class_bytes):
    # Quick regex or parsing of Java class file constant pool to find strings
    # Constant pool starts after magic (4) + version (4) + constant pool count (2)
    # The count is a 16-bit big-endian integer.
    if class_bytes[:4] != b'\xca\xfe\xba\xbe':
        return []
    
    count = int.from_bytes(class_bytes[8:10], byteorder='big')
    strings = []
    offset = 10
    
    # We iterate and parse constant pool tags
    # UTF8 tag is 1, size is 2 bytes + length.
    # We will just find all UTF-8 strings by looking for tag \x01 and then decoding the length.
    # To be fast and robust, let's just find all substrings matching printables or standard paths.
    # Actually, we can use a simpler approach: extract all ascii strings of length >= 3
    # with regex:
    ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
    return [s.decode('utf-8', errors='ignore') for s in ascii_strings]

def main():
    jar_path = 'esignet/esignet-service.jar'
    with zipfile.ZipFile(jar_path, 'r') as z:
        for name in z.namelist():
            if 'controllers/' in name and name.endswith('.class'):
                print(f"=== Strings in {name} ===")
                class_bytes = z.read(name)
                strs = parse_class_strings(class_bytes)
                # Print strings that look like paths or config options
                for s in sorted(set(strs)):
                    if '/' in s or 'well' in s or 'openid' in s or 'jwk' in s:
                        print(f"  {s}")

if __name__ == '__main__':
    main()
