import zipfile
import re

def main():
    jar_path = 'esignet/esignet-service.jar'
    targets = [
        'io/mosip/esignet/core/dto/AuthRequest.class',
        'io/mosip/esignet/core/dto/AuthRequestV2.class'
    ]
    
    with zipfile.ZipFile(jar_path, 'r') as z:
        for name in z.namelist():
            if any(t in name for t in targets):
                print(f"=== Strings in {name} ===")
                class_bytes = z.read(name)
                ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
                decoded = sorted(set([s.decode('utf-8', errors='ignore') for s in ascii_strings]))
                for s in decoded:
                    if len(s) > 2 and '/' not in s and '(' not in s and ';' not in s:
                        print(f"  {s}")

if __name__ == '__main__':
    main()
