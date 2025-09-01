// DocType: Purchases  |  Field: read_scale_button (Button)  |  Under Weight in KG
// Works in secure contexts (https). Chrome/Edge desktop & Android support Web Bluetooth.
// iOS Safari support is limited; we detect and show a helpful error.
console.log('read_scale.js loaded');          // shows in browser devtools
frappe.ui.form.on('Purchases', {
  async read_scale_button(frm) {
    frappe.msgprint("Button click reached handler")
    try {
      // --- Pre-checks ---
      if (!window.isSecureContext) {
        throw new Error("This feature requires HTTPS (secure context). Open your site over https://");
      }
      if (!('bluetooth' in navigator)) {
        throw new Error("Web Bluetooth is not supported in this browser. Try Chrome or Edge on desktop/Android.");
      }

      // Optional: warn if on iOS Safari where Web Bluetooth is typically unsupported
      const ua = navigator.userAgent || '';
      const onIOS = /iPad|iPhone|iPod/.test(ua);
      const onSafari = /^((?!chrome|android).)*safari/i.test(ua);
      if (onIOS && onSafari) {
        throw new Error("Web Bluetooth is not available on iOS Safari. Please use Chrome/Edge on desktop or Android.");
      }

      frappe.show_alert({ message: 'Connecting to scale…', indicator: 'blue' });

      // --- Configure your scale’s BLE service/characteristic here ---
      // Example: Nordic UART Service (NUS). Replace with your scale’s UUIDs if different.
      const SERVICE_UUID = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
      const CHAR_UUID_RX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'; // RX characteristic (device -> client)
      // If your scale uses a different service (e.g., custom), set proper UUIDs.

      // Request device (you can narrow filters by namePrefix or services)
      const device = await navigator.bluetooth.requestDevice({
        filters: [{ services: [SERVICE_UUID] }],
        optionalServices: [SERVICE_UUID]
      });

      // Connect GATT
      const server = await device.gatt.connect();

      // Get service & characteristic
      const service = await server.getPrimaryService(SERVICE_UUID);
      const char = await service.getCharacteristic(CHAR_UUID_RX);

      // --- Read a single value (some scales stream; if yours does, switch to notifications) ---
      // Try notifications first; if not supported, fall back to readValue()
      let weightKg = null;

      const parseWeight = (dataView) => {
        // Parse bytes -> number (kg)
        // Many scales send ASCII like "12.34", others send binary.
        // We try ASCII first, then a simple float32 fallback.

        // Attempt ASCII parse
        let txt = '';
        for (let i = 0; i < dataView.byteLength; i++) {
          const code = dataView.getUint8(i);
          if (code >= 32 && code <= 126) txt += String.fromCharCode(code);
        }
        const ascii = (txt || '').trim();

        // Extract a number from ASCII if present
        const m = ascii.match(/-?\d+(\.\d+)?/);
        if (m) return parseFloat(m[0]);

        // Fallback: try float32 little-endian from first 4 bytes
        if (dataView.byteLength >= 4) {
          try {
            return dataView.getFloat32(0, /*littleEndian=*/true);
          } catch (e) {
            // ignore and fall through
          }
        }
        return null;
      };

      let supportsNotifications = false;
      try {
        await char.startNotifications();
        supportsNotifications = true;
      } catch (e) {
        // Not all characteristics support notifications; we'll read once.
      }

      if (supportsNotifications) {
        // Wait for the first notification then stop notifications
        const valueOnce = await new Promise((resolve, reject) => {
          const onValue = (event) => {
            try {
              const dv = event.target.value;
              const parsed = parseWeight(dv);
              if (parsed != null && isFinite(parsed)) {
                char.removeEventListener('characteristicvaluechanged', onValue);
                resolve(parsed);
              }
            } catch (err) {
              char.removeEventListener('characteristicvaluechanged', onValue);
              reject(err);
            }
          };
          char.addEventListener('characteristicvaluechanged', onValue);
          // Some devices require an initial read or write to trigger streaming.
          // If your scale needs a "wake" command, you could write here.
          // Example (if your TX UUID exists): await txChar.writeValue(new Uint8Array([0x0A]));
          // As a safety, also set a timeout:
          setTimeout(() => reject(new Error("No data received from scale.")), 6000);
        });
        weightKg = valueOnce;
        try { await char.stopNotifications(); } catch (e) { /* ignore */ }
      } else {
        const dv = await char.readValue();
        weightKg = parseWeight(dv);
      }

      if (weightKg == null || !isFinite(weightKg)) {
        throw new Error("Could not parse a valid weight from the scale.");
      }

      // Optional sanity checks (e.g., 0–200 kg)
      if (weightKg < 0 || weightKg > 1000) {
        throw new Error(`Unrealistic weight value received: ${weightKg}`);
      }

      // Round to 2 decimals and set field
      const rounded = Math.round(weightKg * 100) / 100;
      await frm.set_value('weight_in_kg', rounded);
      frappe.show_alert({ message: `Weight set to ${rounded} kg`, indicator: 'green' });

      // Auto-calc total price if you later add a script for that, etc.
    } catch (err) {
      console.error(err);
      frappe.msgprint({
        title: 'Scale Read Error',
        message: __(err.message || 'Failed to read from the Bluetooth scale.'),
        indicator: 'red'
      });
    }
  }
});
