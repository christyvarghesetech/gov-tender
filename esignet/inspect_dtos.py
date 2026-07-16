import zipfile
import re

def main():
    jar_path = 'esignet/esignet-service.jar'
    targets = [
        'io/mosip/esignet/core/dto/PushedOAuthDetailRequest.class',
        'io/mosip/esignet/core/dto/OAuthDetailRequest.class',
        'io/mosip/esignet/core/dto/OAuthDetailRequestV2.class',
        'io/mosip/esignet/core/dto/OAuthDetailRequestV3.class'
    ]
    
    with zipfile.ZipFile(jar_path, 'r') as z:
        # We need to scan zip to find files whose paths match targets (handling potential directory prefixes)
        for name in z.namelist():
            if any(t in name for t in targets):
                print(f"\n=== Strings in {name} ===")
                try:
                    class_bytes = z.read(name)
                    ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
                    decoded = sorted(set([s.decode('utf-8', errors='ignore') for s in ascii_strings]))
                    # Print private fields or standard field-like strings (typically lowerCamelCase without slashes)
                    for s in decoded:
                        if re.match(r'^[a-zA-Z0-9_]+$', s) and not s.isupper() and len(s) > 2:
                            print(f"  {s}")
                except Exception as e:
                    print(f"Error reading {name}: {e}")

if __name__ == '__main__':
    main()
