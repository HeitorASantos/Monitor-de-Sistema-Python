import os
import platform
import socket
import subprocess
import GPUtil
import cpuinfo
import time
import pathlib
from pathlib import Path
import tkinter as tk
from collections import deque
from datetime import datetime, timedelta
from tkinter import ttk
import psutil
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

GPU_FOUND = False
try:
    import pynvml

    pynvml.nvmlInit()
    _gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    GPU_FOUND = True
except Exception:
    GPU_FOUND = False
    _gpu_handle = None

# ---------------------------------------------#
#               >Estilização<
# ---------------------------------------------#
BG = "#121417"
PANEL_BG = "#1b1e23"
FG = "#e6e6e6"
FG_DIM = "#8a8f98"
ACCENT_CPU = "#00B7EB"
ACCENT_RAM = "#7FFFD4"
ACCENT_GPU = "#FF0800"
ACCENT_DISK = "#FF00FF"
TRACK_COLOR = "#2a2e35"
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 12, "bold")
FONT_BIG = ("Segoe UI", 15, "bold")

UPDATE_MS = 1000


# ---------------------------------------------#

def run_cmd(cmd):
    try:
        out = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=2
        )
        return out.decode(errors="ignore").strip()
    except Exception:
        return ""


def get_os_info():
    system = platform.system()
    if system == "Linux":
        try:
            with open("/etc/os-release") as f:
                data = dict(
                    line.strip().split("=", 1)
                    for line in f
                    if "=" in line and not line.startswith("#")
                )
            name = data.get("PRETTY_NAME", "Linux").strip('"')
            return f"{name}"
        except Exception:
            return f"Linux {platform.release()}"
    elif system == "Windows":
        return f"Windows {platform.release()} ({platform.version()})"
    elif system == "Darwin":
        return f"macOS {platform.mac_ver()[0]}"
    return system


def get_host_info():
    try:
        if platform.system() == "Linux":
            vendor = run_cmd(
                "cat /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null"
            )
            product = run_cmd(
                "cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null"
            )
            host = f"{vendor} {product}".strip()
            if host:
                return host
        return platform.node()
    except Exception:
        return platform.node()


def get_packages_count():
    system = platform.system()
    try:
        if system == "Linux":
            for cmd, label in [
                ("dpkg -l 2>/dev/null | grep -c '^ii'", "dpkg"),
                ("rpm -qa 2>/dev/null | wc -l", "rpm"),
                ("pacman -Qq 2>/dev/null | wc -l", "pacman"),
                ("flatpak list 2>/dev/null | wc -l", "flatpak"),
            ]:
                out = run_cmd(cmd)
                if out.isdigit() and int(out) > 0:
                    return f"{out} ({label})"
        elif system == "Darwin":
            out = run_cmd("brew list 2>/dev/null | wc -l")
            if out.isdigit():
                return f"{out} (brew)"
        elif system == "Windows":
            out = run_cmd(
                'powershell -Command "(Get-Package).Count" 2>NUL'
            )
            if out.isdigit():
                return f"{out} (winget/pkg)"
    except Exception:
        pass
    return "N/A"


def get_cpu_info():
    system = platform.system()

    try:

        if system == "Windows":
            return platform.processor() or "CPU desconhecida"


        elif system == "Darwin":
            cmd = ["sysctl", "-n", "machdep.cpu.brand_string"]
            return subprocess.check_output(cmd).decode().strip()


        elif system == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    # Checa "model name" (Intel/AMD) ou "Processor" (ARM/Raspberry Pi)
                    if "model name" in line or "Hardware" in line:
                        return line.split(":", 1)[1].strip()

    except Exception:
        pass

    return platform.processor() or "CPU desconhecida"


def get_gpu_info():
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return "Nenhuma GPU encontrada"
        return " / ".join([gpu.name for gpu in gpus])
    except Exception:
        return "GPU integrada"


def get_de_wm():
    de = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get(
        "DESKTOP_SESSION"
    )
    wm = None
    if platform.system() == "Linux":
        wm = run_cmd("wmctrl -m 2>/dev/null | grep Name | cut -d: -f2").strip()
        if not wm:
            wm = os.environ.get("XDG_SESSION_TYPE")
    elif platform.system() == "Windows":
        de = "Windows Shell"
        wm = "DWM"
    elif platform.system() == "Darwin":
        de = "Aqua"
        wm = "Quartz Compositor"
    return de or "N/A", wm or "N/A"


def get_display_res():
    try:
        root = tk._default_root
        if root:
            return f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}"
    except Exception:
        pass
    return "N/A"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "N/A"


def get_ipv6():
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET6 and not a.address.startswith(
                        "fe80"
                ) and a.address != "::1":
                    return a.address.split("%")[0]
    except Exception:
        pass
    return "N/A"


def get_wifi_ssid():
    system = platform.system()

    try:
        if system == "Linux":
            out = run_cmd(
                "nmcli -t -f DEVICE,TYPE,STATE dev 2>/dev/null"
            )

            wifi_device = None

            for line in out.splitlines():
                parts = line.split(":")

                if len(parts) >= 3:
                    device, dev_type, state = parts[:3]

                    if dev_type == "wifi" and state == "connected":
                        wifi_device = device
                        break

            if not wifi_device:
                return "N/A (cabo/offline)"

            ssid = run_cmd(
                f"nmcli -t -f GENERAL.CONNECTION "
                f"dev show {wifi_device} 2>/dev/null"
            ).strip()

            if ":" in ssid:
                ssid = ssid.split(":", 1)[1].strip()

            return ssid or "N/A"

        elif system == "Windows":
            out = run_cmd("netsh wlan show interfaces")

            for line in out.splitlines():
                line = line.strip()

                if line.startswith("SSID") and not line.startswith("BSSID"):
                    return line.split(":", 1)[1].strip()

            return "N/A (cabo/offline)"
        elif system == "Darwin":
            airport = (
                "/System/Library/PrivateFrameworks/"
                "Apple80211.framework/Versions/Current/Resources/airport"
            )

            out = run_cmd(f"{airport} -I 2>/dev/null")

            for line in out.splitlines():
                line = line.strip()

                if line.startswith("SSID:"):
                    return line.split(":", 1)[1].strip()

            return "N/A (cabo/offline)"

    except Exception:
        return "N/A"

    return "N/A"


def format_bytes(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def format_uptime(seconds):
    d = timedelta(seconds=int(seconds))
    days, rem = divmod(d.seconds + d.days * 86400, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    parts.append(f"{hrs}h")
    parts.append(f"{mins}m")
    return " ".join(parts)


class DonutGauge:
    def __init__(self, parent, title, color, unit="%"):
        self.color = color
        self.unit = unit
        self.frame = tk.Frame(parent, bg=PANEL_BG)
        self.fig = Figure(figsize=(2.1, 2.1), dpi=90, facecolor=PANEL_BG)
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.title_lbl = tk.Label(
            self.frame, text=title, fg=FG, bg=PANEL_BG, font=FONT_BOLD
        )
        self.title_lbl.pack(pady=(0, 6))
        self.update_value(0)

    def update_value(self, value, unavailable=False):
        self.ax.clear()
        self.ax.set_facecolor(PANEL_BG)
        if unavailable:
            value = 0
            label = "N/A"
            color = FG_DIM
        else:
            value = max(0, min(100, value))
            label = f"{value:.0f}{self.unit}"
            color = self.color

        self.ax.pie(
            [value, 100 - value],
            colors=[color, TRACK_COLOR],
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.32, edgecolor=PANEL_BG, linewidth=2),
        )
        self.ax.text(
            0,
            0,
            label,
            ha="center",
            va="center",
            fontsize=17,
            fontweight="bold",
            color=FG if not unavailable else FG_DIM,
        )
        self.ax.set_aspect("equal")
        self.canvas.draw_idle()

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)


class SystemMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Sistema")
        self.root.configure(bg=BG)
        self.root.geometry("1180x800")
        self.root.minsize(1000, 720)
        self._setup_style()

        net = psutil.net_io_counters()
        self._last_net = (net.bytes_sent, net.bytes_recv, time.time())

        # Dicionário
        self.static_info = {
            "os": get_os_info(),
            "host": get_host_info(),
            "packages": get_packages_count(),
            "display": get_display_res(),
            "CPU": get_cpu_info(),
            "GPU": get_gpu_info(),
        }
        self.static_info["de"], self.static_info["wm"] = get_de_wm()

        self._build_layout()
        self._wifi_cache = ("N/A", 0)

        self.update_loop()

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            background=PANEL_BG,
            fieldbackground=PANEL_BG,
            foreground=FG,
            rowheight=24,
            borderwidth=0,
            font=FONT_MAIN,
        )
        style.configure(
            "Treeview.Heading",
            background="#22262d",
            foreground=FG,
            font=FONT_BOLD,
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#31414f")])

    def _section_frame(self, parent, title):
        outer = tk.Frame(parent, bg=PANEL_BG, highlightbackground="#2a2e35",
                         highlightthickness=1)
        header = tk.Label(
            outer, text=title, bg=PANEL_BG, fg=FG, font=FONT_TITLE, anchor="w"
        )
        header.pack(fill="x", padx=12, pady=(10, 4))
        return outer

    def _build_layout(self):
        root = self.root
        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=1)
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)

        gauges_frame = tk.Frame(root, bg=BG)
        gauges_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        for i in range(4):
            gauges_frame.grid_columnconfigure(i, weight=1)

        self.gauge_cpu = DonutGauge(gauges_frame, "CPU", ACCENT_CPU)
        self.gauge_ram = DonutGauge(gauges_frame, "RAM", ACCENT_RAM)
        self.gauge_gpu = DonutGauge(gauges_frame, "GPU", ACCENT_GPU)
        self.gauge_disk = DonutGauge(gauges_frame, "Armazenamento", ACCENT_DISK)
        self.gauge_cpu.grid(row=0, column=0, sticky="nsew", padx=8)
        self.gauge_ram.grid(row=0, column=1, sticky="nsew", padx=8)
        self.gauge_gpu.grid(row=0, column=2, sticky="nsew", padx=8)
        self.gauge_disk.grid(row=0, column=3, sticky="nsew", padx=8)

        chart_section = self._section_frame(root, "Consumo por segundo")
        chart_section.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        self.history_time = deque(maxlen=60)
        self.history_cpu = deque(maxlen=60)
        self.history_ram = deque(maxlen=60)
        self.history_gpu = deque(maxlen=60)
        self.history_disk = deque(maxlen=60)

        self.usage_fig = Figure(
            figsize=(8, 3.2),
            dpi=90,
            facecolor=PANEL_BG,
        )
        self.usage_ax = self.usage_fig.add_subplot(111)
        self.usage_fig.subplots_adjust(
            left=0.07, right=0.98, top=0.88, bottom=0.22
        )

        self.usage_canvas = FigureCanvasTkAgg(
            self.usage_fig,
            master=chart_section,
        )
        self.usage_canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12),
        )

        self._configure_usage_chart()

        bottom = tk.Frame(root, bg=BG)
        bottom.grid(row=2, column=0, sticky="nsew", padx=14, pady=(8, 14))
        bottom.grid_columnconfigure(0, weight=2)
        bottom.grid_columnconfigure(1, weight=1)
        bottom.grid_rowconfigure(0, weight=1)

        sysinfo_section = self._section_frame(bottom, "Informações do sistema")
        sysinfo_section.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.sys_labels = {}
        sys_fields = [
            "OS", "Host", "Uptime", "CPU", "GPU", "Packages", "Display", "DE", "WM",
            "IP Local", "Memória", "Disco", "Bateria",
        ]
        grid_inner = tk.Frame(sysinfo_section, bg=PANEL_BG)
        grid_inner.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        for i, field in enumerate(sys_fields):
            r, c = divmod(i, 2)
            cell = tk.Frame(grid_inner, bg=PANEL_BG)
            cell.grid(row=r, column=c, sticky="w", padx=(0, 24), pady=5)
            tk.Label(
                cell, text=f"{field}:", bg=PANEL_BG, fg=FG_DIM, font=FONT_MAIN
            ).pack(side="left")
            val_lbl = tk.Label(
                cell, text="...", bg=PANEL_BG, fg=FG, font=FONT_BOLD
            )
            val_lbl.pack(side="left", padx=(6, 0))
            self.sys_labels[field] = val_lbl

        net_section = self._section_frame(bottom, "Rede")
        net_section.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        net_inner = tk.Frame(net_section, bg=PANEL_BG)
        net_inner.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.net_labels = {}
        net_fields = ["Wi-Fi", "Download", "Upload", "IPv4", "IPv6"]
        for field in net_fields:
            row = tk.Frame(net_inner, bg=PANEL_BG)
            row.pack(fill="x", pady=5, anchor="w")
            tk.Label(
                row, text=f"{field}:", bg=PANEL_BG, fg=FG_DIM, font=FONT_MAIN,
                width=10, anchor="w",
            ).pack(side="left")
            val_lbl = tk.Label(row, text="...", bg=PANEL_BG, fg=FG, font=FONT_BOLD)
            val_lbl.pack(side="left")
            self.net_labels[field] = val_lbl

    def _configure_usage_chart(self):
        self.usage_ax.set_facecolor(PANEL_BG)
        self.usage_ax.set_ylim(0, 100)
        self.usage_ax.set_ylabel("Uso (%)", color=FG)
        self.usage_ax.set_xlabel("Horário", color=FG)
        self.usage_ax.set_title("Consumo de recursos por segundo", color=FG, fontsize=10, fontweight="bold", loc="left",
                                pad=10, )

        self.usage_ax.tick_params(axis="x", colors=FG_DIM, labelsize=8)
        self.usage_ax.tick_params(axis="y", colors=FG_DIM, labelsize=8)

        for spine in self.usage_ax.spines.values():
            spine.set_color("#2a2e35")

        self.usage_ax.grid(True, axis="y", color="#2a2e35", alpha=0.7, linewidth=0.8, )
        self.usage_ax.grid(False, axis="x")

    def _update_usage_chart(self):

        self.usage_ax.clear()
        self._configure_usage_chart()

        if not self.history_time:
            self.usage_canvas.draw_idle()
            return

        x = list(range(len(self.history_time)))

        self.usage_ax.plot(
            x,
            list(self.history_cpu),
            label="CPU",
            color=ACCENT_CPU,
            linewidth=2,
            marker="o",
            markersize=2.5,
        )
        self.usage_ax.plot(
            x,
            list(self.history_ram),
            label="RAM",
            color=ACCENT_RAM,
            linewidth=2,
            marker="o",
            markersize=2.5,
        )

        gpu_values = list(self.history_gpu)
        if any(value is not None for value in gpu_values):
            gpu_plot = [
                float(value) if value is not None else float("nan")
                for value in gpu_values
            ]
            self.usage_ax.plot(
                x, gpu_plot,
                label="GPU",
                color=ACCENT_GPU,
                linewidth=2,
                marker="o",
                markersize=2.5,
            )

        labels = list(self.history_time)
        max_labels = 8

        if len(labels) <= max_labels:
            tick_positions = list(range(len(labels)))
        else:
            step = max(1, (len(labels) - 1) // (max_labels - 1))
            tick_positions = list(range(0, len(labels), step))
            if tick_positions[-1] != len(labels) - 1:
                tick_positions.append(len(labels) - 1)

        self.usage_ax.set_xticks(tick_positions)
        self.usage_ax.set_xticklabels(
            [labels[i] for i in tick_positions],
            color=FG_DIM,
            fontsize=8,
        )

        self.usage_ax.legend(
            loc="upper left",
            ncol=4,
            frameon=False,
            labelcolor=FG,
            fontsize=8,
            handlelength=2.2,
        )

        self.usage_canvas.draw_idle()

    def _get_gpu_percent(self):
        if not GPU_FOUND:
            return None
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_gpu_handle)
            return float(util.gpu)
        except Exception:
            return None

    def _get_battery_text(self):
        try:
            batt = psutil.sensors_battery()
            if batt is None:
                return "N/A (sem bateria)"
            status = "Carregando" if batt.power_plugged else "Descarregando"
            return f"{batt.percent:.0f}% ({status})"
        except Exception:
            return "N/A"

    def _get_disk_percent_and_text(self):
        try:
            usage = psutil.disk_usage("/")
            return usage.percent, f"{format_bytes(usage.used)} / {format_bytes(usage.total)} ({usage.percent:.0f}%)"
        except Exception:
            return 0, "N/A"

    def _get_mem_percent_and_text(self):
        try:
            mem = psutil.virtual_memory()
            return mem.percent, f"{format_bytes(mem.used)} / {format_bytes(mem.total)} ({mem.percent:.0f}%)"
        except Exception:
            return 0, "N/A"

    def _get_network_speed(self):
        net = psutil.net_io_counters()
        now = time.time()
        last_sent, last_recv, last_t = self._last_net
        dt = max(now - last_t, 1e-3)
        up = (net.bytes_sent - last_sent) / dt
        down = (net.bytes_recv - last_recv) / dt
        self._last_net = (net.bytes_sent, net.bytes_recv, now)
        return down, up

    def update_loop(self):
        try:
            self._tick()
        except Exception as e:
            print(f"[monitor] erro na atualização: {e}")
        self.root.after(UPDATE_MS, self.update_loop)

    def _tick(self):
        now = datetime.now()

        cpu_pct = psutil.cpu_percent(interval=None)
        mem_pct, mem_txt = self._get_mem_percent_and_text()
        disk_pct, disk_txt = self._get_disk_percent_and_text()
        gpu_pct = self._get_gpu_percent()

        self.gauge_cpu.update_value(cpu_pct)
        self.gauge_ram.update_value(mem_pct)
        self.gauge_disk.update_value(disk_pct)
        if gpu_pct is None:
            self.gauge_gpu.update_value(0, unavailable=True)
        else:
            self.gauge_gpu.update_value(gpu_pct)

        self.history_time.append(now.strftime("%H:%M:%S"))
        self.history_cpu.append(float(cpu_pct))
        self.history_ram.append(float(mem_pct))
        self.history_gpu.append(
            float(gpu_pct) if gpu_pct is not None else None
        )
        self.history_disk.append(float(disk_pct))
        self._update_usage_chart()

        self.sys_labels["OS"].config(text=self.static_info["os"])
        self.sys_labels["Host"].config(text=self.static_info["host"])
        self.sys_labels["Uptime"].config(text=format_uptime(time.time() - psutil.boot_time()))
        self.sys_labels["CPU"].config(text=self.static_info["CPU"])
        self.sys_labels["GPU"].config(text=self.static_info["GPU"])
        self.sys_labels["Packages"].config(text=self.static_info["packages"])
        self.sys_labels["Display"].config(text=self.static_info["display"])
        self.sys_labels["DE"].config(text=self.static_info["de"])
        self.sys_labels["WM"].config(text=self.static_info["wm"])
        self.sys_labels["IP Local"].config(text=get_local_ip())
        self.sys_labels["Memória"].config(text=mem_txt)
        self.sys_labels["Disco"].config(text=disk_txt)
        self.sys_labels["Bateria"].config(text=self._get_battery_text())

        ssid, ts = self._wifi_cache
        if time.time() - ts > 10:
            ssid = get_wifi_ssid()
            self._wifi_cache = (ssid, time.time())
        down, up = self._get_network_speed()
        self.net_labels["Wi-Fi"].config(text=ssid)
        self.net_labels["Download"].config(text=f"{format_bytes(down)}/s")
        self.net_labels["Upload"].config(text=f"{format_bytes(up)}/s")
        self.net_labels["IPv4"].config(text=get_local_ip())
        self.net_labels["IPv6"].config(text=get_ipv6())


def main():
    root = tk.Tk()
    app = SystemMonitorApp(root)
    BASE_DIR = Path(__file__).resolve().parent

    root.mainloop()


if __name__ == "__main__":
    main()