import os
import psutil
from typing import Dict, Optional


class MemoryMonitor:
    def __init__(self, device_index: int = 0):
        self.process = psutil.Process(os.getpid())
        self.device_index = device_index
        self.gpu_available = False
        self.nvml_handle = None

        try:
            import pynvml

            pynvml.nvmlInit()
            self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
            self.gpu_available = True
        except Exception as e:
            print(f"Warning: GPU monitoring not available: {e}")
            pass

    def get_ram_usage(self) -> float:
        """Returns the current process RSS memory usage in MB."""
        mem_info = self.process.memory_info()
        return mem_info.rss / (1024 * 1024)

    def get_vram_usage(self) -> float:
        """Returns the current process GPU memory usage in MB. If process-specific usage is not available (e.g. WSL2), returns global usage."""
        if not self.gpu_available:
            return 0.0

        import pynvml

        process_usage = 0.0
        try:
            # Try to get process-specific memory usage
            compute_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(
                self.nvml_handle
            )
            graphics_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(
                self.nvml_handle
            )

            my_pid = self.process.pid

            for p in compute_procs + graphics_procs:
                if p.pid == my_pid:
                    # usedGpuMemory is in bytes
                    process_usage += p.usedGpuMemory / (1024 * 1024)

            # Fallback for WSL2 or if process not found but GPU is used
            if process_usage == 0.0:
                info = pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
                return info.used / (1024 * 1024)

            return process_usage

        except Exception:
            # Final fallback to global if anything fails
            try:
                info = pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
                return info.used / (1024 * 1024)
            except:
                return 0.0

    def get_global_vram_usage(self) -> float:
        """Returns the global GPU memory usage in MB (all processes)."""
        if not self.gpu_available:
            return 0.0
        import pynvml

        info = pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
        return info.used / (1024 * 1024)

    def get_current_usage(self) -> Dict[str, float]:
        """Returns a dictionary with 'ram' and 'vram' usage in MB."""
        return {"ram": self.get_ram_usage(), "vram": self.get_vram_usage()}

    def print_usage(self, label: str = ""):
        usage = self.get_current_usage()
        prefix = f"[{label}] " if label else ""
        print(f"{prefix}RAM: {usage['ram']:.2f} MB | VRAM: {usage['vram']:.2f} MB")

    def __del__(self):
        if self.gpu_available:
            try:
                import pynvml

                pynvml.nvmlShutdown()
            except:
                pass
