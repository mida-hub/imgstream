# ImgStream API仕様書

このドキュメントは、ImgStream写真管理アプリケーションの包括的なAPIドキュメントを提供します。

## 📋 目次

- [概要](#概要)
- [認証](#認証)
- [ベースURL](#ベースurl)
- [共通ヘッダー](#共通ヘッダー)
- [エラーハンドリング](#エラーハンドリング)
- [レート制限](#レート制限)
- [ヘルスチェックエンドポイント](#ヘルスチェックエンドポイント)
- [写真管理エンドポイント](#写真管理エンドポイント)
- [ユーザー管理エンドポイント](#ユーザー管理エンドポイント)
- [データモデル](#データモデル)
- [例](#例)

## 🌐 概要

ImgStream APIは、アップロード、保存、取得、メタデータ管理を含む写真管理機能を提供するRESTful Webサービスです。APIはFastAPIを使用して構築され、OpenAPI 3.0仕様に従っています。

### APIバージョン

- **現在のバージョン**: v1
- **ベースパス**: `/api/v1`
- **プロトコル**: HTTPS のみ
- **フォーマット**: JSON

### 機能

- 安全な写真のアップロードと保存
- サムネイル生成
- メタデータ管理
- Google Cloud IAPによるユーザー認証
- リアルタイムヘルス監視
- 包括的なエラーハンドリング

## 🔐 Authentication

### Production Environment

ImgStream uses Google Cloud Identity-Aware Proxy (IAP) for authentication in production environments.

**Authentication Flow:**
1. User accesses the application through IAP
2. IAP validates user identity
3. IAP forwards request with JWT token
4. Application validates JWT token

**Headers:**
```http
Authorization: Bearer <IAP_JWT_TOKEN>
X-Goog-IAP-JWT-Assertion: <IAP_JWT_TOKEN>
```

### Development Environment

Development environment bypasses authentication for easier testing.

**Headers:**
```http
X-Development-User: dev@example.com
```

### Authentication Errors

| Status Code | Error | Description |
|-------------|-------|-------------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | User lacks required permissions |

## 🌍 Base URLs

| Environment | Base URL |
|-------------|----------|
| Development | `http://localhost:8501/api/v1` |
| Staging | `https://imgstream-staging.example.com/api/v1` |
| Production | `https://imgstream.example.com/api/v1` |

## 📤 Common Headers

### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | `application/json` for JSON requests |
| `Authorization` | Yes* | Bearer token for authentication |
| `X-Request-ID` | No | Unique request identifier for tracing |
| `User-Agent` | No | Client application identifier |

*Required in staging and production environments

### Response Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | Response content type |
| `X-Request-ID` | Request identifier for tracing |
| `X-RateLimit-Limit` | Rate limit maximum requests |
| `X-RateLimit-Remaining` | Remaining requests in current window |
| `X-RateLimit-Reset` | Rate limit reset timestamp |

## ⚠️ Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional error details"
    },
    "request_id": "req_123456789",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request parameters |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists |
| 413 | Payload Too Large - File size exceeds limit |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |
| 503 | Service Unavailable - Service temporarily unavailable |

### Common Error Codes

| Error Code | Description |
|------------|-------------|
| `INVALID_REQUEST` | Request format or parameters are invalid |
| `AUTHENTICATION_FAILED` | Authentication token is invalid or expired |
| `PERMISSION_DENIED` | User lacks required permissions |
| `RESOURCE_NOT_FOUND` | Requested resource does not exist |
| `RESOURCE_ALREADY_EXISTS` | Resource with same identifier already exists |
| `FILE_TOO_LARGE` | Uploaded file exceeds size limit |
| `INVALID_FILE_TYPE` | File type is not supported |
| `STORAGE_ERROR` | Error accessing storage service |
| `RATE_LIMIT_EXCEEDED` | Too many requests in time window |
| `INTERNAL_ERROR` | Unexpected server error |

## 🚦 Rate Limiting

### Limits by Environment

| Environment | Requests per Minute | Burst Limit |
|-------------|-------------------|-------------|
| Development | Unlimited | Unlimited |
| Staging | 100 | 200 |
| Production | 60 | 120 |

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642248600
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again later.",
    "details": {
      "limit": 60,
      "reset_time": "2024-01-15T10:35:00Z"
    }
  }
}
```

## 🏥 Health Check Endpoints

### GET /health

Comprehensive health check for all application components.

**Request:**
```http
GET /health
Accept: application/json
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 3600,
  "environment": "production",
  "version": "1.0.0",
  "checks": {
    "database": {
      "healthy": true,
      "response_time_ms": 5.2,
      "database_type": "DuckDB"
    },
    "storage": {
      "healthy": true,
      "storage_type": "Google Cloud Storage",
      "bucket": "imgstream-prod-bucket",
      "response_time_ms": 120.5
    },
    "authentication": {
      "healthy": true,
      "auth_type": "IAP",
      "development_mode": false
    },
    "configuration": {
      "healthy": true,
      "environment": "production",
      "issues": []
    }
  }
}
```

### GET /ready

Lightweight readiness check for load balancers and orchestrators.

**Request:**
```http
GET /ready
```

**Response:**
```json
{
  "ready": true,
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database": true,
    "storage": true
  }
}
```

## 📸 Photo Management Endpoints

### POST /photos

Upload a new photo with metadata.

**Request:**
```http
POST /photos
Content-Type: multipart/form-data
Authorization: Bearer <token>

--boundary
Content-Disposition: form-data; name="file"; filename="photo.jpg"
Content-Type: image/jpeg

[binary image data]
--boundary
Content-Disposition: form-data; name="title"

My Photo Title
--boundary
Content-Disposition: form-data; name="description"

Photo description
--boundary--
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | Image file (JPEG, PNG, WebP) |
| `title` | String | No | Photo title (max 255 chars) |
| `description` | String | No | Photo description (max 1000 chars) |
| `tags` | String | No | Comma-separated tags |
| `private` | Boolean | No | Whether photo is private (default: false) |

**Response:**
```json
{
  "id": "photo_123456789",
  "title": "My Photo Title",
  "description": "Photo description",
  "filename": "photo.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 1048576,
  "width": 1920,
  "height": 1080,
  "tags": ["nature", "landscape"],
  "private": false,
  "upload_date": "2024-01-15T10:30:00Z",
  "user_id": "user_987654321",
  "urls": {
    "original": "https://storage.googleapis.com/bucket/photos/photo_123456789.jpg",
    "thumbnail": "https://storage.googleapis.com/bucket/thumbnails/photo_123456789_thumb.jpg"
  },
  "metadata": {
    "camera": "Canon EOS R5",
    "lens": "RF 24-70mm f/2.8L IS USM",
    "iso": 100,
    "aperture": "f/8.0",
    "shutter_speed": "1/125",
    "focal_length": "35mm"
  }
}
```

### GET /photos

List user's photos with pagination and filtering.

**Request:**
```http
GET /photos?page=1&limit=20&tags=nature&private=false&sort=upload_date&order=desc
Authorization: Bearer <token>
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | Integer | 1 | Page number (1-based) |
| `limit` | Integer | 20 | Items per page (max 100) |
| `tags` | String | - | Filter by tags (comma-separated) |
| `private` | Boolean | - | Filter by privacy setting |
| `sort` | String | `upload_date` | Sort field (`upload_date`, `title`, `size`) |
| `order` | String | `desc` | Sort order (`asc`, `desc`) |
| `search` | String | - | Search in title and description |

**Response:**
```json
{
  "photos": [
    {
      "id": "photo_123456789",
      "title": "My Photo Title",
      "description": "Photo description",
      "filename": "photo.jpg",
      "content_type": "image/jpeg",
      "size_bytes": 1048576,
      "width": 1920,
      "height": 1080,
      "tags": ["nature", "landscape"],
      "private": false,
      "upload_date": "2024-01-15T10:30:00Z",
      "urls": {
        "thumbnail": "https://storage.googleapis.com/bucket/thumbnails/photo_123456789_thumb.jpg"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_items": 150,
    "total_pages": 8,
    "has_next": true,
    "has_previous": false
  }
}
```

### GET /photos/{photo_id}

Get detailed information about a specific photo.

**Request:**
```http
GET /photos/photo_123456789
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "photo_123456789",
  "title": "My Photo Title",
  "description": "Photo description",
  "filename": "photo.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 1048576,
  "width": 1920,
  "height": 1080,
  "tags": ["nature", "landscape"],
  "private": false,
  "upload_date": "2024-01-15T10:30:00Z",
  "user_id": "user_987654321",
  "urls": {
    "original": "https://storage.googleapis.com/bucket/photos/photo_123456789.jpg?signed_url_expires=3600",
    "thumbnail": "https://storage.googleapis.com/bucket/thumbnails/photo_123456789_thumb.jpg"
  },
  "metadata": {
    "camera": "Canon EOS R5",
    "lens": "RF 24-70mm f/2.8L IS USM",
    "iso": 100,
    "aperture": "f/8.0",
    "shutter_speed": "1/125",
    "focal_length": "35mm",
    "gps": {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "altitude": 100
    }
  },
  "stats": {
    "views": 42,
    "downloads": 5,
    "last_accessed": "2024-01-15T09:15:00Z"
  }
}
```

### PUT /photos/{photo_id}

Update photo metadata.

**Request:**
```http
PUT /photos/photo_123456789
Content-Type: application/json
Authorization: Bearer <token>

{
  "title": "Updated Photo Title",
  "description": "Updated description",
  "tags": ["nature", "landscape", "sunset"],
  "private": true
}
```

**Response:**
```json
{
  "id": "photo_123456789",
  "title": "Updated Photo Title",
  "description": "Updated description",
  "tags": ["nature", "landscape", "sunset"],
  "private": true,
  "updated_date": "2024-01-15T10:35:00Z"
}
```

### DELETE /photos/{photo_id}

Delete a photo and its associated files.

**Request:**
```http
DELETE /photos/photo_123456789
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Photo deleted successfully",
  "deleted_at": "2024-01-15T10:40:00Z"
}
```

### GET /photos/{photo_id}/download

Download the original photo file.

**Request:**
```http
GET /photos/photo_123456789/download
Authorization: Bearer <token>
```

**Response:**
```http
HTTP/1.1 302 Found
Location: https://storage.googleapis.com/bucket/photos/photo_123456789.jpg?signed_url
Content-Type: image/jpeg
```

### GET /photos/{photo_id}/thumbnail

Get photo thumbnail.

**Request:**
```http
GET /photos/photo_123456789/thumbnail?size=medium
Authorization: Bearer <token>
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | String | `medium` | Thumbnail size (`small`, `medium`, `large`) |

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Content-Length: 15360
Cache-Control: public, max-age=3600

[binary image data]
```

## 👤 User Management Endpoints

### GET /user/profile

Get current user profile information.

**Request:**
```http
GET /user/profile
Authorization: Bearer <token>
```

**Response:**
```json
{
  "user_id": "user_987654321",
  "email": "user@example.com",
  "name": "John Doe",
  "avatar_url": "https://example.com/avatar.jpg",
  "created_date": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-15T10:00:00Z",
  "settings": {
    "default_private": false,
    "auto_generate_thumbnails": true,
    "max_file_size": 104857600
  },
  "stats": {
    "total_photos": 150,
    "total_storage_bytes": 1073741824,
    "photos_this_month": 25
  }
}
```

### PUT /user/settings

Update user settings.

**Request:**
```http
PUT /user/settings
Content-Type: application/json
Authorization: Bearer <token>

{
  "default_private": true,
  "auto_generate_thumbnails": true,
  "max_file_size": 52428800
}
```

**Response:**
```json
{
  "settings": {
    "default_private": true,
    "auto_generate_thumbnails": true,
    "max_file_size": 52428800
  },
  "updated_date": "2024-01-15T10:45:00Z"
}
```

## 📊 Data Models

### Photo Model

```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "filename": "string",
  "content_type": "string",
  "size_bytes": "integer",
  "width": "integer",
  "height": "integer",
  "tags": ["string"],
  "private": "boolean",
  "upload_date": "string (ISO 8601)",
  "updated_date": "string (ISO 8601)",
  "user_id": "string",
  "urls": {
    "original": "string (URL)",
    "thumbnail": "string (URL)"
  },
  "metadata": {
    "camera": "string",
    "lens": "string",
    "iso": "integer",
    "aperture": "string",
    "shutter_speed": "string",
    "focal_length": "string",
    "gps": {
      "latitude": "number",
      "longitude": "number",
      "altitude": "number"
    }
  },
  "stats": {
    "views": "integer",
    "downloads": "integer",
    "last_accessed": "string (ISO 8601)"
  }
}
```

### User Model

```json
{
  "user_id": "string",
  "email": "string",
  "name": "string",
  "avatar_url": "string",
  "created_date": "string (ISO 8601)",
  "last_login": "string (ISO 8601)",
  "settings": {
    "default_private": "boolean",
    "auto_generate_thumbnails": "boolean",
    "max_file_size": "integer"
  },
  "stats": {
    "total_photos": "integer",
    "total_storage_bytes": "integer",
    "photos_this_month": "integer"
  }
}
```

### Error Model

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object",
    "request_id": "string",
    "timestamp": "string (ISO 8601)"
  }
}
```

## 💡 Examples

### Upload Photo with cURL

```bash
curl -X POST "https://imgstream.example.com/api/v1/photos" \
  -H "Authorization: Bearer $IAP_TOKEN" \
  -F "file=@photo.jpg" \
  -F "title=Beautiful Sunset" \
  -F "description=Sunset over the mountains" \
  -F "tags=nature,sunset,mountains"
```

### List Photos with Python

```python
import requests

headers = {
    'Authorization': f'Bearer {iap_token}',
    'Content-Type': 'application/json'
}

response = requests.get(
    'https://imgstream.example.com/api/v1/photos',
    headers=headers,
    params={
        'page': 1,
        'limit': 10,
        'tags': 'nature',
        'sort': 'upload_date',
        'order': 'desc'
    }
)

photos = response.json()['photos']
for photo in photos:
    print(f"{photo['title']}: {photo['urls']['thumbnail']}")
```

### JavaScript Fetch Example

```javascript
// Upload photo
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('title', 'My Photo');
formData.append('tags', 'nature,landscape');

fetch('/api/v1/photos', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${iapToken}`
  },
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('Photo uploaded:', data);
})
.catch(error => {
  console.error('Upload failed:', error);
});
```

## 🔗 OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:
- **Development**: `http://localhost:8501/docs`
- **Staging**: `https://imgstream-staging.example.com/docs`
- **Production**: `https://imgstream.example.com/docs`

## 📝 Changelog

### Version 1.0.0 (2024-01-15)
- Initial API release
- Photo upload and management endpoints
- User profile management
- Health check endpoints
- Comprehensive error handling
- Rate limiting implementation

---

For additional support or questions about the API, please contact the development team or create an issue in the GitHub repository.
