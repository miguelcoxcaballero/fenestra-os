/*
 * fprintd shim for dual boot with Windows Hello on match-on-chip sensors.
 *
 * fprintd wipes the whole sensor ("clear storage before first enrollment")
 * when it has no local prints. On a dual-boot laptop that erases the
 * fingerprints Windows stored on the same sensor. This turns that wipe into a
 * successful no-op; deleting a single print (fprintd-delete) still works.
 */
#include <gio/gio.h>

typedef struct _FpDevice FpDevice;

gboolean
fp_device_clear_storage_sync (FpDevice *device, GCancellable *cancellable, GError **error)
{
  (void) device; (void) cancellable; (void) error;
  g_message ("dual-boot: kept fingerprint sensor storage (clear skipped)");
  return TRUE;
}
