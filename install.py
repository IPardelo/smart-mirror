#!/usr/bin/env python3
"""Instala dependencias, crea o venv e configura o autostart na Raspberry Pi."""

import os
import subprocess
import sys
from pathlib import Path


def run(cmd, check=True, **kwargs):
    print('+', ' '.join(cmd) if isinstance(cmd, list) else cmd)
    return subprocess.run(cmd, check=check, **kwargs)


def main():
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)

    autostart_dir = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'autostart'
    desktop_file = autostart_dir / 'smart-mirror.desktop'
    venv_python = script_dir / '.venv' / 'bin' / 'python'

    print(f'==> Smart Mirror: instalación en {script_dir}')

    print('==> Dependencias do sistema (sudo)...')
    run(['sudo', 'apt-get', 'update'])
    run(['sudo', 'apt-get', 'install', '-y', 'python3-tk', 'python3-venv', 'python3-full', 'locales'])

    print('==> Locale galego (gl_ES.UTF-8)...')
    run(['sudo', 'sed', '-i', '/^# *gl_ES.UTF-8/s/^# *//', '/etc/locale.gen'])
    run(['sudo', 'locale-gen', 'gl_ES.UTF-8'])

    print('==> Entorno virtual e paquetes Python...')
    run([sys.executable, '-m', 'venv', '.venv'])
    run([str(script_dir / '.venv' / 'bin' / 'pip'), 'install', '--upgrade', 'pip'])
    run([str(script_dir / '.venv' / 'bin' / 'pip'), 'install', '-r', 'requirements.txt'])

    run_script = script_dir / 'run-mirror.sh'
    run_script.write_text(
        '''#!/usr/bin/env bash
# Agarda á rede antes de abrir o espello (arranque automatico na Pi).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export DISPLAY="${DISPLAY:-:0}"
LOG="$SCRIPT_DIR/smartmirror.log"

log() {
  echo "$(date -Iseconds) run-mirror: $*" >> "$LOG"
}

log "agardando rede..."
for i in $(seq 1 90); do
  if ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 || ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
    log "rede dispoñible (intento $i)"
    break
  fi
  if [[ "$i" -eq 90 ]]; then
    log "rede non detectada; iniciando igualmente"
  fi
  sleep 2
done

sleep 3
/usr/bin/xset s off -dpms s noblank 2>/dev/null || true
log "lanzando smartmirror.py"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/smartmirror.py"
''',
        encoding='utf-8',
        newline='\n',
    )
    run_script.chmod(0o755)

    print(f'==> Arranque automatico: {desktop_file}')
    autostart_dir.mkdir(parents=True, exist_ok=True)
    exec_line = f'"{run_script}"'
    desktop_file.write_text(
        '\n'.join(
            [
                '[Desktop Entry]',
                'Type=Application',
                'Name=Smart Mirror',
                'Comment=Espello intelixente',
                f'Exec={exec_line}',
                f'Path={script_dir}',
                'Terminal=false',
                'X-GNOME-Autostart-Delay=15',
                'X-GNOME-Autostart-enabled=true',
                '',
            ]
        ),
        encoding='utf-8',
        newline='\n',
    )

    print()
    print('Instalación completada.')
    print(f'  Probar agora:  {venv_python} {script_dir / "smartmirror.py"}')
    print(f'  Autostart:     {desktop_file}')
    print('  Pantalla completa ao arrancar: activada en smartmirror.py')
    print('  Locale galego: gl_ES.UTF-8 (comproba con: locale -a | grep gl_ES)')
    print()
    print('Reinicia para aplicar locale e autostart: sudo reboot')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
