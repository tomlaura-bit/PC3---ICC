# Documentación técnica PC3 Tienda LocalStack

## Propósito

La solución implementa una tienda académica desplegada en contenedores. La aplicación permite consultar un catálogo, agregar productos al carrito y comprar. Cada compra se persiste en DynamoDB y se publica en SQS. El panel administrativo permite revisar pedidos y almacenar imágenes de usuario en S3.

## Componentes

### Aplicación FastAPI

Expone la interfaz web y los endpoints REST. Valida cantidades, calcula precios desde el catálogo persistido y evita aceptar precios enviados por el navegador. El acceso administrativo utiliza una cookie firmada, HTTP-only y con duración limitada.

### DynamoDB

`pc3-products` usa `product_id` como clave de partición. `pc3-orders` usa `order_id`. Los precios y totales se almacenan como `Decimal` para evitar errores de punto flotante.

### SQS

`pc3-orders-queue` recibe un mensaje por pedido con identificador, usuario, total y fecha. El envío ocurre después de guardar el pedido. La cola desacopla la compra de un futuro consumidor de procesamiento.

### S3

`pc3-user-images` guarda imágenes bajo `users/{user_id}/{uuid}-{filename}`. La aplicación restringe la carga a tipos MIME de imagen y conserva el `Content-Type`.

### Docker y WSL

Docker Compose levanta LocalStack y la aplicación. LocalStack persiste datos en un volumen. La aplicación espera el health check antes de iniciar y crea los recursos de forma idempotente.

## Seguridad del laboratorio

La solución no usa los perfiles AWS del equipo. Los contenedores reciben credenciales ficticias `test/test` y un endpoint LocalStack explícito. La contraseña administrativa es solo de demostración y debe cambiarse para un entorno distinto.

## Flujo de un pedido

1. El navegador solicita el catálogo a FastAPI.
2. El usuario forma el carrito y envía identificadores/cantidades.
3. FastAPI obtiene cada producto de DynamoDB y calcula el total.
4. El pedido se guarda en `pc3-orders`.
5. Se publica el aviso en `pc3-orders-queue`.
6. El panel administrativo consulta pedidos y atributos de la cola.

## Simulación

`scripts/simulate_orders.py` genera usuarios y carritos aleatorios. Envía cada pedido a la API para ejercitar el mismo flujo que la interfaz. Con `--count 100` se crean cien registros y cien mensajes.

## Decisiones y límites

- La cola no se consume porque la evaluación exige evidenciar los pedidos pendientes en SQS.
- La autenticación es apropiada para un laboratorio local; producción requeriría un proveedor de identidad, TLS y secretos externos.
- El listado administrativo usa scan por el pequeño volumen académico. Un sistema real usaría claves e índices para consultas eficientes.
