import zipfile
import re

def main():
    jar_path = 'esignet/esignet-service.jar'
    target_class = 'BOOT-INF/classes/io/mosip/esignet/controllers/AuthorizationController.class'
    
    with zipfile.ZipFile(jar_path, 'r') as z:
        class_bytes = z.read(target_class)
        # Find all ASCII strings of length >= 3
        ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
        decoded = sorted(set([s.decode('utf-8', errors='ignore') for s in ascii_strings]))
        
        print(f"=== Strings in {target_class} ===")
        for s in decoded:
            if any(term in s.lower() for term in ['oauth-details', 'dto', 'requestwrapper', 'responsewrapper']):
                print(f"  {s}")

if __name__ == '__main__':
    main()
