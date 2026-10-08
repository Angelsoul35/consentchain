# 04 — El registro en la cadena (on-chain)

## ¿Para qué una cadena aquí?

No para pagar ni para "cripto", sino para tener un **registro del
consentimiento a prueba de manipulación y auditable por todas las partes**. Un
paciente, una clínica, una aseguradora y un auditor pueden necesitar una fuente
de verdad común sobre qué se autorizó y cuándo, que nadie pueda cambiar en
secreto. Eso es justo lo que da un libro mayor en cadena.

El contrato es `contracts/src/ConsentRegistry.sol`.

## Qué guarda el contrato

Por cada trío `(paciente, solicitante, propósito)`:

- `categoryMask` (uint16): las categorías permitidas, como bits.
- `expiry` (uint64): segundos Unix de caducidad.
- `version` (uint32): sube con cada `grant` o `revoke`.

Y dos contadores globales: `totalGrants` y `totalRevocations`.

La clave del mapa es `keccak256(patient, requester, purpose)`, así que cada trío
tiene su propia entrada.

## Las funciones

- `grant(patient, requester, purpose, categoryMask, expiry)`: registra (o
  reemplaza) un consentimiento. Sube la versión y emite `ConsentGranted`.
- `revoke(patient, requester, purpose)`: pone la máscara a 0, sube la versión y
  emite `ConsentRevoked`.
- `consentOf(...)`: lee la máscara, la caducidad y la versión.
- `hasConsent(patient, requester, purpose, requiredMask)`: devuelve `true` solo
  si no ha caducado **y** `categoryMask & requiredMask == requiredMask`.

## Privacidad: nada personal ni clínico en la cadena

Una cadena es permanente y muy replicada. Nunca debemos escribir en ella datos de
salud ni identidades, por dos razones: la ley (un libro inmutable no puede
cumplir un borrado) y la seguridad básica.

Por eso en la cadena solo hay datos **estructurales y no identificativos**:

- paciente y solicitante son un `bytes32` (el hash keccak de un identificador
  estable que vive **fuera** de la cadena);
- las categorías son posiciones de bit;
- el propósito es un entero pequeño.

El texto de la petición, el nombre del paciente, los valores clínicos y la
correspondencia id↔persona se quedan fuera, bajo el control del operador. Así se
mantiene la auditabilidad **sin** sacrificar la privacidad, y el "derecho al
olvido" sigue siendo posible: borrar la correspondencia rompe el vínculo, y en la
cadena solo quedan ids opacos.

## Solo el operador puede escribir

El contrato tiene un modificador `onlyOperator`. Solo el servicio de gestión de
consentimiento (que actúa siguiendo la instrucción del paciente) puede
`grant`/`revoke`. Si otro lo intenta, revierte con `NotOperator`. Esto impide que
alguien falsifique un consentimiento.

Además hay guardas de entrada, con **errores personalizados** (más baratos en gas
y más claros que cadenas de texto):

- `ZeroParty`: ni paciente ni solicitante pueden ser el id cero.
- `EmptyScope`: no se registra un consentimiento con máscara 0.
- `PastExpiry`: la caducidad debe estar en el futuro.

## El historial auditable

Cada cambio emite un evento (`ConsentGranted` / `ConsentRevoked`) con la versión.
Reproduciendo los eventos se reconstruye la línea de tiempo completa del
consentimiento: qué se concedió, qué se revocó y cuándo. Nadie puede reescribir
ese historial sin que se note.

## El fake en memoria

Igual que en otros proyectos, hay dos clientes que cumplen el mismo `Protocol`
(`RegistryClient`): `Web3RegistryClient` (habla con el contrato real) y
`InMemoryRegistryClient` (imita la contabilidad en un diccionario, con las mismas
guardas). Una prueba concede el mismo consentimiento en los dos y comprueba que
coinciden, para que el fake no se desvíe del contrato. Esto mantiene las pruebas
rápidas y permite usar la API sin cadena.

## Para fijar la idea

- La cadena aporta un **registro de consentimiento auditable e inmutable**.
- Solo datos estructurales y `bytes32`: **sin** nombres ni datos clínicos.
- `onlyOperator` + guardas con errores personalizados → nadie falsifica consentimiento.
- Los eventos versionados reconstruyen todo el historial.
- El fake, validado contra el contrato, mantiene las pruebas rápidas y honestas.
