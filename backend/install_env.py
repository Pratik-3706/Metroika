"""
Automated PaddlePaddle + PaddleOCR installer.

Detects NVIDIA GPU and CUDA version, then installs the correct
PaddlePaddle build (GPU or CPU). Includes:
- Multi-index fallback (cu126 → cu123 → cu118 → CPU)
- Conflict resolution (uninstalls CPU version before GPU install)
- Post-install verification (imports paddle and checks CUDA)
"""

import subprocess
import sys
import re
import importlib


# Paddle version and OCR versions to install
PADDLE_VERSION = "3.3.0"
PADDLEOCR_VERSION = "3.7.0"
PADDLEX_VERSION = "3.7.2"

# Ordered list of CUDA index URLs to try (newest first)
GPU_INDICES = [
    ("cu126", "https://www.paddlepaddle.org.cn/packages/stable/cu126/"),
    ("cu123", "https://www.paddlepaddle.org.cn/packages/stable/cu123/"),
    ("cu118", "https://www.paddlepaddle.org.cn/packages/stable/cu118/"),
]
CPU_INDEX = "https://www.paddlepaddle.org.cn/packages/stable/cpu/"


def detect_cuda() -> tuple:
    """Detect NVIDIA GPU and CUDA version via nvidia-smi.
    
    Returns:
        (cuda_detected: bool, major: int, minor: int)
    """
    try:
        result = subprocess.run(
            ['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", result.stdout)
            if match:
                return True, int(match.group(1)), int(match.group(2))
            else:
                print("[!] NVIDIA GPU found but couldn't parse CUDA version from nvidia-smi.")
                return False, 0, 0
    except FileNotFoundError:
        pass
    
    print("[*] nvidia-smi not found — no NVIDIA GPU detected.")
    return False, 0, 0


def get_ordered_indices(major: int, minor: int) -> list:
    """Get CUDA index URLs ordered by best match for the detected CUDA version.
    
    PaddlePaddle GPU wheels are forward-compatible within a major CUDA version,
    so cu118 works on CUDA 12.x, but cu126 is preferred if available.
    """
    # Map CUDA version to the best starting index
    if major >= 12:
        if minor >= 6:
            preferred = ["cu126", "cu123", "cu118"]
        elif minor >= 3:
            preferred = ["cu123", "cu126", "cu118"]
        else:
            preferred = ["cu118", "cu123", "cu126"]
    elif major == 11:
        preferred = ["cu118"]
    else:
        preferred = ["cu118"]
    
    # Build ordered list based on preference
    ordered = []
    for tag in preferred:
        for idx_tag, idx_url in GPU_INDICES:
            if idx_tag == tag:
                ordered.append((idx_tag, idx_url))
                break
    return ordered


def remove_conflicting_packages():
    """Remove CPU-only paddlepaddle to prevent it from shadowing the GPU version."""
    print("[*] Removing any conflicting CPU-only paddlepaddle...")
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "paddlepaddle", "-y"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def install_gpu(indices: list) -> bool:
    """Try installing paddlepaddle-gpu from each index in order. Returns True on success."""
    remove_conflicting_packages()
    
    for tag, url in indices:
        print(f"\n[*] Trying PaddlePaddle GPU from index: {tag} ...")
        try:
            subprocess.check_call(
                [
                    sys.executable, "-m", "pip", "install",
                    f"paddlepaddle-gpu=={PADDLE_VERSION}",
                    "--extra-index-url", url,
                ],
                stdout=sys.stdout, stderr=sys.stderr
            )
            print(f"[+] paddlepaddle-gpu=={PADDLE_VERSION} installed from {tag}.")
            return True
        except subprocess.CalledProcessError:
            print(f"[!] Index {tag} failed, trying next...")
            continue
    
    return False


def install_cpu():
    """Install CPU-only paddlepaddle as fallback."""
    print("\n[*] Installing PaddlePaddle CPU version as fallback...")
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install",
            f"paddlepaddle=={PADDLE_VERSION}",
            "--extra-index-url", CPU_INDEX,
        ],
        stdout=sys.stdout, stderr=sys.stderr
    )
    print(f"[+] paddlepaddle=={PADDLE_VERSION} (CPU) installed.")


def install_ocr():
    """Install PaddleOCR and PaddleX."""
    print("\n[*] Installing PaddleOCR and PaddleX...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        f"paddleocr=={PADDLEOCR_VERSION}", f"paddlex=={PADDLEX_VERSION}"
    ])
    print(f"[+] PaddleOCR {PADDLEOCR_VERSION} and PaddleX {PADDLEX_VERSION} installed.")


def verify_installation() -> bool:
    """Verify PaddlePaddle is importable and check GPU availability."""
    print("\n[*] Verifying installation...")
    try:
        result = subprocess.run(
            [
                sys.executable, "-c",
                "import paddle; "
                "gpu = paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0; "
                "print('GPU_AVAILABLE=' + str(gpu)); "
                "print('VERSION=' + paddle.__version__); "
                "print('DEVICE=' + ('GPU:' + str(paddle.device.cuda.device_count()) if gpu else 'CPU'))"
            ],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        print(f"    {output.replace(chr(10), chr(10) + '    ')}")
        
        if result.returncode != 0:
            print(f"[!] Verification failed: {result.stderr}")
            return False
        
        if "GPU_AVAILABLE=True" in output:
            print("[+] PaddlePaddle GPU is working!")
            return True
        else:
            print("[!] PaddlePaddle installed but GPU not detected by paddle.")
            return False
            
    except Exception as e:
        print(f"[!] Verification error: {e}")
        return False


def main():
    print("=" * 56)
    print("   Metroika - PaddleOCR Hardware-Optimized Installer   ")
    print("=" * 56)
    
    cuda_detected, major, minor = detect_cuda()
    
    gpu_success = False
    if cuda_detected:
        print(f"\n[+] Detected NVIDIA GPU with CUDA {major}.{minor}")
        indices = get_ordered_indices(major, minor)
        print(f"[*] Will try indices: {[t for t, _ in indices]}")
        
        gpu_success = install_gpu(indices)
        
        if gpu_success:
            # Verify it actually works
            if not verify_installation():
                print("\n[!] GPU installation didn't pass verification.")
                print("[*] Falling back to CPU version...")
                # Clean up broken GPU install and go CPU
                subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", "paddlepaddle-gpu", "-y"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                install_cpu()
                gpu_success = False
        else:
            print("\n[!] All GPU indices failed.")
            print("[*] Falling back to CPU version...")
            install_cpu()
    else:
        install_cpu()
    
    # Install PaddleOCR
    install_ocr()
    
    # Final summary
    print("\n" + "=" * 56)
    if gpu_success:
        print("  [+] Setup complete - PaddleOCR running on GPU")
    else:
        print("  [+] Setup complete - PaddleOCR running on CPU")
        if cuda_detected:
            print("    (GPU was detected but installation failed)")
    print("=" * 56)


if __name__ == "__main__":
    main()
