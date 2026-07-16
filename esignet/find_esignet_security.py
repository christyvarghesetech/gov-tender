import zipfile
import os

def scan_zip(zip_path, is_nested=False):
    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('.class') and 'io/mosip/esignet' in name and ('Security' in name or 'Config' in name or 'Csrf' in name or 'Filter' in name):
                print(f"Found class: {name}")
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
