import zipfile
import re
import os

def scan_zip(zip_path, is_nested=False):
    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('.class') and 'io/mosip/esignet/core/dto' in name:
                try:
                    class_bytes = z.read(name)
                    if any(term in class_bytes for term in [b'otp', b'password', b'pin', b'otpCode', b'credential', b'authCode']):
                        # Print strings inside this class
                        ascii_strings = re.findall(b'[\x20-\x7e]{3,}', class_bytes)
                        decoded = sorted(set([s.decode('utf-8', errors='ignore') for s in ascii_strings]))
                        fields = [s for s in decoded if len(s) > 2 and '/' not in s and '(' not in s and ';' not in s]
                        if fields:
                            print(f"\nClass: {name}")
                            for f in fields:
                                if any(t in f.lower() for t in ['otp', 'password', 'pin', 'val', 'code', 'factor', 'challenge']):
                                    print(f"  {f}")
                except Exception:
                    pass
            elif name.endswith('.jar') and not is_nested:
                try:
                    nested_data = z.read(name)
                    temp_name = 'temp_sec_find.jar'
                    with open(temp_name, 'wb') as f:
                        f.write(nested_data)
                    scan_zip(temp_name, is_nested=True)
                    os.remove(temp_name)
                except Exception:
                    pass

def main():
    scan_zip('esignet/esignet-service.jar')

if __name__ == '__main__':
    main()
