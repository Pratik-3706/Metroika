import subprocess
import sys
import re

def main():
    print("====================================================")
    print("      Detecting Hardware for PaddleOCR Setup        ")
    print("====================================================")
    
    cuda_detected = False
    cu_version = "cpu"
    
    try:
        # Check nvidia-smi
        result = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            # Look for "CUDA Version: XX.X"
            match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", result.stdout)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                
                cuda_detected = True
                if major == 11:
                    cu_version = "cu118"
                elif major == 12:
                    if minor >= 6:
                        cu_version = "cu126"
                    elif minor >= 3:
                        cu_version = "cu123"
                    else:
                        cu_version = "cu118" # Fallback for early CUDA 12 versions
                else:
                    cu_version = "cu118"
                
                print(f"[*] Detected NVIDIA GPU with CUDA {major}.{minor}.")
            else:
                print("[!] NVIDIA GPU found but couldn't parse CUDA version.")
    except FileNotFoundError:
        print("[*] nvidia-smi not found (No NVIDIA GPU detected).")

    if cuda_detected:
        print(f"[*] Installing PaddlePaddle GPU version (Index: {cu_version})...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "paddlepaddle-gpu==3.3.0", 
            "--extra-index-url", f"https://www.paddlepaddle.org.cn/packages/stable/{cu_version}/"
        ])
    else:
        print("[*] Installing PaddlePaddle CPU version...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "paddlepaddle==3.3.0", 
            "--extra-index-url", "https://www.paddlepaddle.org.cn/packages/stable/cpu/"
        ])

    print("[*] Installing PaddleOCR and dependencies...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "paddleocr==3.7.0", "paddlex==3.7.2"
    ])
    
    print("\n[+] Hardware-specific dependencies installed successfully!")

if __name__ == "__main__":
    main()
