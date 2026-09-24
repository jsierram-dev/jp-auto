"""Hace que Python confíe en los mismos certificados que Windows (y el navegador).

Los antivirus que analizan HTTPS (p. ej. Avast) firman las conexiones con su propia raíz, que solo está en
el almacén de Windows: sin esto, requests (certifi) las rechaza. Basta con importar este módulo; cada
módulo que se conecta a internet lo importa para funcionar también cuando se ejecuta suelto.
"""

import truststore

truststore.inject_into_ssl()
