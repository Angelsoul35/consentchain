# 01 — El modelo de consentimiento

## El problema: el consentimiento no es un interruptor

En salud, el consentimiento no es un simple "sí" o "no". Un paciente puede
aceptar compartir **algunos** tipos de datos, con **algunos** solicitantes, para
**algunos** propósitos y durante **un tiempo limitado**.

Ejemplo real:

- Acepto que mi cardiólogo vea mis **resultados de laboratorio** para **tratarme**.
- **No** acepto que un grupo de investigación use mis **datos genéticos** para un
  **estudio**.

Un sistema que modela el consentimiento como una sola casilla ("¿puede esta
clínica ver mi historia?") no puede expresar esa diferencia. Y cuando no puedes
expresarla, los datos se filtran. Por eso ConsentChain usa un modelo más rico.

## Las tres dimensiones

Un registro de consentimiento se identifica por el **trío**
`(paciente, solicitante, propósito)` y guarda:

- una **máscara de categorías**: un entero de 16 bits, un bit por cada categoría
  de datos;
- una **caducidad** (`expiry`): segundos Unix a partir de los cuales ya no vale;
- una **versión**: sube con cada cambio (cada `grant` o `revoke`).

### Propósitos

Cuatro, inspirados en un modelo que los profesionales ya conocen:

- `TREATMENT` (tratamiento)
- `PAYMENT` (pago / facturación)
- `OPERATIONS` (operaciones internas, auditoría de calidad)
- `RESEARCH` (investigación)

### Categorías de datos (los bits de la máscara)

`DEMOGRAPHICS`, `DIAGNOSES`, `MEDICATIONS`, `LAB_RESULTS`, `IMAGING`, `GENETIC`,
`MENTAL_HEALTH`, `BILLING`. Cada una es una potencia de dos, así que un conjunto
de categorías es un solo número: si combinas `DIAGNOSES` (bit 1 = 2) y
`LAB_RESULTS` (bit 3 = 8), la máscara es 10.

## Las tres reglas

El modelo hace que las reglas sean baratísimas de comprobar:

1. **Por propósito (purpose-scoped):** un propósito distinto es una clave
   distinta. El consentimiento para tratamiento **nunca** autoriza investigación.
2. **Exacto por categoría (category-exact):** se permite solo si
   `concedido & solicitado == solicitado`. Es decir, lo concedido debe cubrir
   **todas** las categorías solicitadas.
3. **Con caducidad (time-bound):** vale solo mientras `expiry > ahora`. Un
   consentimiento caducado es **ningún** consentimiento.

### ¿Por qué una máscara de bits?

Porque comprobar "¿lo concedido cubre lo solicitado?" es una sola operación
`AND` de bits: `granted & requested == requested`. Es rápido, exacto y encaja
perfectamente en la EVM, que trabaja con enteros. Además, todo el alcance de un
consentimiento cabe en un único número de 16 bits.

El límite es 16 categorías. Para este dominio sobra, y ampliarlo más adelante
sería un cambio en el contrato, no un rediseño.

## Para fijar la idea

- El consentimiento tiene **cuatro dimensiones**: quién, a quién, para qué y qué
  datos (más hasta cuándo).
- El trío `(paciente, solicitante, propósito)` + máscara + caducidad + versión lo
  captura todo.
- Las tres reglas son comparaciones simples, ideales para la cadena.
- La versión que sube en cada cambio es lo que hace auditable el historial.
