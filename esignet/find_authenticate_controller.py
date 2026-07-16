import zipfile
import re

def main():
    jar_path = 'esignet/esignet-service.jar'
    target = 'BOOT-INF/classes/io/mosip/esignet/controllers/AuthorizationController.class'
    
    with zipfile.ZipFile(jar_path, 'r') as z:
        print(f"=== Strings in {target} ===")
        class_bytes = z.read(target)
        # Extract all ascii strings of length >= 3
        ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
        decoded = sorted(set([s.decode('utf-8', errors='ignore') for s in ascii_strings]))
        for s in decoded:
            if 'authenticate' in s.lower() or 'auth' in s.lower():
                print(f"  {s}")

if __name__ == '__main__':
    main()
