# Zeta Finance · Panel de análisis

Tablero de lectura técnica de unos 130 CEDEARs para los clientes de Zeta Finance. Los precios salen de Yahoo Finance. No es una recomendación de inversión.

## Cómo correrlo

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run cedear_dashboard.py
```

Entrá con el usuario y la contraseña que hayas puesto en `secrets.toml`.

## Secretos

`.streamlit/secrets.toml` no se commitea. El formato es el mismo de siempre:

```toml
[passwords]
cliente = "cambiar-esta-clave"

# Opcional. Si falta, el aviso muestra Matrícula N° ___.
matricula = "___"
```

`passwords` es una tabla de usuario → contraseña. La matrícula CNV se edita en `matricula` o, si preferís dejarla en el código, en `MATRICULA_CNV` dentro de `zeta/marca.py`.

## Qué muestra

Resumen, monitor, análisis por activo, radar de fuerza relativa, rotación sectorial (ETF de sector e índices contra SPY), carteras modelo y metodología. En la barra se elige el tema Oscuro (el de entrada) o Claro; queda en la sesión. El encabezado muestra `Datos actualizados` con la hora de Argentina de la última descarga (no la de abrir la página), si la rueda de CEDEARs está abierta y la demora de Yahoo. **Actualizar datos** vuelve a pedir los precios. El corte de las 18:00 también usa `America/Argentina/Buenos_Aires`.
