# Rescate: Fedora 45 + Fenestra no pasa de la pantalla negra

Guía para el agente que trabaja en el Fedora del portátil. El agente de Windows del mismo equipo la
escribió el 2026-11-06 con lo que encontró desde Windows.

## Síntoma
- Portátil Samsung Galaxy Book 940XGK con arranque dual (Windows 11 + Fedora/Fenestra).
- Tras actualizar a Fedora 45 (GNOME 51) desde Configuración › Fenestra Update, la pantalla se queda en negro.
  Al pulsar Enter aparece **la pantalla de contraseña del usuario (avatar + nombre, es decir, GDM)** durante menos de 1 s
  y vuelve a negro. Pasa con todos los kernels y con el rescue.
- Ahora el usuario entra por consola de texto (GRUB: `systemd.unit=multi-user.target`).

## Causa probable (por confirmar)
En GNOME 51 ya no existe `Meta.Background.set_file`. Las extensiones fenestra-login (GDM), fenestra-spotlight y
fenestra-lock-clock lo usan en `face.js` para dibujar el fondo. El arreglo está en la rama
`wip/fedora45-notepad-paint` de este repo, pero el portátil tiene la versión antigua.

## Comprobado desde Windows
- Disco 0 (Samsung 990 EVO 2TB): p1 MSR, p2 NTFS «Data» (D:, **ahí está el pagefile de Windows**), p3 EFI 600 MB,
  p4 XBOOTLDR 2 GB (/boot), **p5 btrfs SIN cifrar, etiqueta `fedora`, 521 GB** (subvolúmenes `root` y `home`).
- Disco 1 (Samsung 512 GB): Windows (EFI, C:, recuperación). **No tocar.**
- Desde Windows no se pudo montar Fedora: WinBtrfs 1.10 lo bloquea la política de integridad de código (evento 3077) y
  `wsl --mount` falla porque el pagefile en D: bloquea el disco 0. En Fedora **no se ha cambiado nada**.
- En Windows sigue instalado, sin cargar, el paquete del driver WinBtrfs (oem211.inf / oem216.inf). Lo quitará el agente
  de Windows si el usuario quiere.

## Qué hacer (en este orden)
1. Si el usuario ya ejecutó el script `r` de esta rama, lee `/root/fenestra-rescate.log` (`sudo cat`). Si no:
   `curl -L raw.githubusercontent.com/miguelcoxcaballero/fenestra-os/rescate/r | sudo bash`
   El script solo lee, salvo que encuentre `set_file is not a function` en el journal. En ese caso mueve (no borra)
   las carpetas `fenestra-{login,spotlight,lock-clock}@fenestra-os.github.io` de `extensions/` a
   `disabled-fenestra-*` junto a `extensions/`, en `/usr/share/gnome-shell`, `/var/lib/gdm/.local/share/gnome-shell`
   y `~/.local/share/gnome-shell`.
2. Si la causa **no** es `set_file`: no muevas nada. Investiga con `journalctl -b -1 -u gdm`, `journalctl -b -1 _COMM=gnome-shell`,
   `/var/lib/fenestra/release-upgrade.json` y si existe `/system-update` (actualización offline a medias). Explícaselo al usuario antes de cambiar nada.
3. Si `/usr` es de solo lectura (sistema atómico/ostree), `mv` fallará. No fuerces nada: avisa al usuario.
4. Tras moverlas: `sudo reboot` sin parámetros extra en GRUB. Debe salir el GDM normal de GNOME, sin el aspecto de Fenestra.
5. Ya en el escritorio, instala las versiones arregladas de las tres extensiones desde la rama
   `wip/fedora45-notepad-paint` (revisa antes que `face.js` ya no usa `set_file`). Después vuelve a habilitarlas.
   Solo cuando funcionen, propón al usuario borrar las carpetas `disabled-fenestra-*`.

## Estado (2026-11-06, rama fix/fedora45-login)
Causa confirmada y reproducida en el banco `tests/greeter/bench.sh` (GNOME 51, contenedor fedora:45).
La explicación completa, lo probado y lo que falta están en `docs/login-safety.md`.

**Para volver al login de Fenestra** (pasos separados, ninguno reinicia GDM):
1. `sudo bash extras/fedora-upgrade/fix-local-services.sh --dry-run` y después sin `--dry-run`
   (howdy-preload, galaxy-book-guard y Howdy en el login de GDM 51).
2. `sudo bash extras/fedora-upgrade/restore-login-extensions.sh`: instala el guardián del login y
   las copias corregidas, y activa solo windows-spotlight. Comprueba el bloqueo (Super+L) y la
   pantalla de inicio de sesión.
3. `sudo bash extras/fedora-upgrade/restore-login-extensions.sh --enable-login`: el reloj de Fenestra.
4. Si algo falla: Ctrl+Alt+F3, inicia sesión y ejecuta `sudo bash extras/fedora-upgrade/restore-login-extensions.sh --rollback`.

## Reglas
- No borres ni reinstales nada. Si cambias algo, que sea reversible (mover o renombrar) y deja constancia en el log.
- No toques la EFI, GRUB, el disco 1 ni las particiones de Windows/D:.
- No ejecutes `btrfs check --repair` ni herramientas de reparación.
