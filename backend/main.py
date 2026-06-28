import sys
import uvicorn

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8080
    
    print("\n" + "=" * 60)
    print(" GovTender Integrated Portal Server is Starting...")
    print(f" Click the link to open the portal: http://{host}:{port}/")
    print("=" * 60 + "\n")
    
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
