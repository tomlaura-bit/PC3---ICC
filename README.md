# PC3 Tienda LocalStack

Aplicación web de compras para la PC3 de Introducción a Cognitive Computing. Implementa catálogo, carrito, compra, acceso administrador, DynamoDB, almacenamiento de imágenes en S3, publicación de pedidos en SQS y ejecución en contenedores Docker sobre WSL 2.

## Arquitectura

```text
Navegador -> FastAPI (puerto 8000)
                 |-> DynamoDB: pc3-products y pc3-orders
                 |-> S3: pc3-user-images
                 `-> SQS: pc3-orders-queue
                          |
                    LocalStack (puerto 4566)
```

Todo se ejecuta localmente. Las credenciales `test/test` son ficticias y solo se usan contra `http://localstack:4566` o `http://localhost:4566`.

## Requisitos

- Windows 10/11 con WSL 2.
- Docker Desktop con motor Linux activo.
- Docker Compose v2.

## Ejecución

Desde PowerShell, en esta carpeta:

```powershell
docker compose up -d --build
docker compose ps
```

Abrir <http://localhost:8000>.

Credenciales locales de demostración:

```text
Usuario: admin
Contraseña: Admin123!
```

No reutilizar estas credenciales fuera del laboratorio.

## Flujo de demostración

1. Agregar productos al carrito y realizar una compra.
2. Ingresar como administrador.
3. Consultar los pedidos almacenados en DynamoDB y el número de mensajes SQS.
4. Seleccionar una imagen y subirla al bucket S3 local.
5. Ejecutar el simulador de 100 pedidos.

```powershell
docker compose exec app python scripts/simulate_orders.py --count 100
```

Cada petición crea un registro en DynamoDB y publica un mensaje en SQS.

## Verificación por AWS CLI

Los comandos incluyen el endpoint local de forma explícita para impedir acceso accidental a AWS real:

```powershell
$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_DEFAULT_REGION = "us-east-1"

aws dynamodb list-tables --endpoint-url http://localhost:4566
aws dynamodb scan --table-name pc3-orders --select COUNT --endpoint-url http://localhost:4566
aws s3 ls s3://pc3-user-images --recursive --endpoint-url http://localhost:4566
$queue = aws sqs get-queue-url --queue-name pc3-orders-queue --endpoint-url http://localhost:4566 --query QueueUrl --output text
aws sqs get-queue-attributes --queue-url $queue --attribute-names ApproximateNumberOfMessages --endpoint-url http://localhost:4566
```

## Endpoints principales

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/health` | Estado de aplicación y recursos locales |
| GET | `/api/products` | Catálogo DynamoDB |
| POST | `/api/orders` | Crea pedido y publica mensaje SQS |
| POST | `/api/login` | Autentica administrador |
| GET | `/api/admin/orders` | Lista pedidos DynamoDB |
| GET | `/api/admin/queue` | Consulta atributos SQS |
| POST | `/api/admin/users/{id}/image` | Sube imagen a S3 |

La documentación interactiva está en <http://localhost:8000/docs>.

## Evidencias

```powershell
powershell -ExecutionPolicy Bypass -File scripts/capture_evidence.ps1
```

El script guarda salidas verificables en `evidence/` sin incluir secretos.

## Limpieza

```powershell
docker compose down
```

Para borrar también los datos persistidos del laboratorio:

```powershell
docker compose down -v
```

## Video de máximo cinco minutos

1. 0:00–0:30: arquitectura y contenedores.
2. 0:30–1:30: catálogo, carrito y compra.
3. 1:30–2:30: login y pedidos en DynamoDB.
4. 2:30–3:15: imagen de usuario en S3.
5. 3:15–4:15: simulador y mensajes en SQS.
6. 4:15–5:00: evidencias Docker/AWS CLI y cierre.
