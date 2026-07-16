import zipfile
import re

def main():
    jar_path = 'esignet/esignet-service.jar'
    print(f"Searching for 'oauth-details' in {jar_path}...")
    with zipfile.ZipFile(jar_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('.class'):
                try:
                    class_bytes = z.read(name)
                    if b'oauth-details' in class_bytes:
                        print(f"Found in: {name}")
                except Exception as e:
                    pass

if __name__ == '__main__':
    main()
