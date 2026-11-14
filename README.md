# TaskHub API — Task Management API

A production-ready Task Management API built with **FastAPI 0.111+**, **SQLAlchemy 2.x Async**, **Alembic**, **Pydantic v2**, **PostgreSQL 18**, and **Layered Architecture**.

---

## 1. Kiến trúc hệ thống (Layered Architecture)

Dự án tuân thủ nghiêm ngặt mô hình phân tầng (Separation of Concerns):

```
Client Request
      │
      ▼
┌──────────────┐
│  API Router  │  app/api/v1/ (endpoints, request validation, routing)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Service    │  app/services/ (business logic, domain validations)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Repository  │  app/repositories/ (abstract CRUD, data storage)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Data Storage │  In-memory (Session 1) ➔ SQLAlchemy 2.x Async (Session 2)
└──────────────┘
```

---

## 2. Đáp ứng chi tiết các Feedback & Review từ Trainer

| Yêu cầu / Review của Trainer | Cách giải quyết trong Session 1 | Vị trí code |
| :--- | :--- | :--- |
| **Exception & Message**<br>Không raise `HTTPException` hardcode text, dùng custom exception kế thừa `AppException`, handler global, message riêng. | Tạo phân cấp `AppException` (`NotFoundException`, `UnauthorizedException`, ...), handler global format response chuẩn JSON, message gom tập trung trong `messages.py`. 401 giữ header `WWW-Authenticate: Bearer`. | `app/core/exceptions.py`<br>`app/core/exception_handlers.py`<br>`app/core/messages.py` |
| **Magic Strings & Constants**<br>Không để magic string "access"/"refresh", "HS256"... | Đưa toàn bộ vào Enums: `TokenType`, `TaskStatus`, `TaskPriority`, `UserRole`, `WorkspaceRole`. Constants: `MIN_PASSWORD_LENGTH`, `MAX_PASSWORD_BYTES = 72`. | `app/core/constants.py` |
| **Annotated Dependency Injection**<br>Dùng `Annotated` thay vì `= Depends(...)`. | Định nghĩa `TaskServiceDep`, `PaginationDep`, `TaskFilterDep`, `SettingsDep` qua `Annotated[..., Depends(...)]`. | `app/core/dependencies.py` |
| **Pydantic v2 Base Schema**<br>Tự động strip whitespace, validate strictly, không để null gây 500. | `AppBaseModel` bật `str_strip_whitespace=True`, `from_attributes=True`. Schemas có min/max rõ ràng. | `app/schemas/base.py`<br>`app/schemas/task.py` |
| **Fail-fast Settings**<br>`SECRET_KEY` không được rỗng, validate min_length. `echo` lấy từ settings. | `pydantic-settings` `BaseSettings` với `SECRET_KEY = Field(..., min_length=32)`, `DB_ECHO = False`. Đầy đủ `.env.example`. | `app/core/config.py`<br>`.env.example` |
| **Lifespan Context**<br>Không dùng `@app.on_event` deprecated. | Dùng `@asynccontextmanager` cho startup & shutdown events. | `app/main.py` |
| **Số lượng file PR & Test**<br>PR Day 1 dưới ~20 file, không có script test tay ở root. Có test tự động. | Cấu trúc tinh gọn ~18 files chính, test tự động bằng `pytest` + `httpx.AsyncClient`. | `tests/` |

---

## 3. Cấu trúc thư mục (Project Structure)

```
taskhub/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory & lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py           # V1 route aggregator
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── health.py       # Health check endpoint
│   │           └── tasks.py        # Task CRUD endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Fail-fast settings (pydantic-settings)
│   │   ├── constants.py            # Enums & constants (no magic strings)
│   │   ├── messages.py             # Centralized message strings
│   │   ├── exceptions.py           # Custom AppException hierarchy
│   │   ├── exception_handlers.py   # Global exception handlers
│   │   └── dependencies.py         # Annotated dependency injection
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract BaseRepository[T]
│   │   └── task.py                 # TaskRepository implementation
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── base.py                 # AppBaseModel, PaginatedResponse, ErrorResponse
│   │   └── task.py                 # TaskBase, TaskCreate, TaskUpdate, TaskResponse
│   └── services/
│       ├── __init__.py
│       └── task.py                 # TaskService (Business logic)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Test fixtures & async client
│   ├── test_health.py              # Health check tests
│   └── test_tasks.py               # CRUD & validation tests
├── .env.example                    # Sample environment variables
├── .env                            # Local development environment
├── .gitignore                      # Git ignore file
├── pyproject.toml                  # Project config, dependencies, ruff & mypy
└── README.md                       # Documentation
```

---

## 4. Hướng dẫn cài đặt và chạy ứng dụng

### 4.1. Chuẩn bị môi trường

Yêu cầu: **Python 3.11+**

```bash
# Di chuyển vào thư mục dự án
cd taskhub

# Khởi tạo file .env từ .env.example (nếu chưa có)
cp .env.example .env
```

### 4.2. Khởi chạy Server (Local Development)

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI (OpenAPI Docs)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: `GET http://localhost:8000/api/v1/health`

---

## 5. Danh sách API Endpoints (Session 1: Task Resource)

| Method | Endpoint | Mô tả | Mã HTTP |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Kiểm tra trạng thái hệ thống | `200 OK` |
| `POST` | `/api/v1/tasks` | Tạo task mới | `201 Created` |
| `GET` | `/api/v1/tasks` | Danh sách tasks (hỗ trợ phân trang `page`, `page_size`, lọc `status`, `priority`, tìm kiếm `search`) | `200 OK` |
| `GET` | `/api/v1/tasks/{id}` | Lấy chi tiết 1 task | `200 OK` / `404 Not Found` |
| `PATCH`| `/api/v1/tasks/{id}` | Cập nhật một phần task | `200 OK` / `404 Not Found` |
| `DELETE`| `/api/v1/tasks/{id}` | Xóa task | `204 No Content` / `404 Not Found` |

---

## 6. Kiểm tra chất lượng Code (Linting, Typing & Testing)

### 6.1. Chạy Unit & Integration Tests

```bash
python -m pytest tests -v
```

### 6.2. Kiểm tra Lint & Format với Ruff (100% pass)

```bash
python -m ruff check app tests
python -m ruff format --check app tests
```

### 6.3. Kiểm tra kiểu dữ liệu với Mypy (Strict mode)

```bash
python -m mypy app
```

