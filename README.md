# Memory MCP

Production-grade **Memory MCP** server for single-tenant LibreChat workspaces. It stores raw conversation turns, distills durable memory (decisions/constraints/mistakes/assumptions/open questions), and provides hybrid retrieval plus plan consistency auditing.

## Özellikler

- **Raw turn log** + embedding + full-text indeksleme.
- **Distilled memory** çıkarımı: kararlar, kısıtlar, hatalar, varsayımlar, açık sorular.
- **Dedup + supersede zinciri** (eski kararlar korunur, stale tespit yapılır).
- **Hybrid retrieval**: pgvector + PostgreSQL full-text + RRF fusion.
- **Fast / Deep modlar**: öngörülebilir gecikme, token budget yönetimi.
- **Audit**: plan/metinleri aktif karar/kısıtlar ve superseded öğelerle kontrol.
- **Shared import/export**: HMAC imzalı paketlerle kontrollü paylaşım.
- **Gözlemlenebilirlik**: JSON log + Prometheus metrikleri.

## Kurulum

### 1) Ortam değişkenleri

`.env` dosyasını `.env.example` üzerinden oluşturun:

```bash
cp .env.example .env
```

Özellikle şunları ayarlayın:

- `DATABASE_URL`
- `LLM_API_KEY`
- `SHARED_HMAC_SECRET`

### 2) Docker Compose

```bash
make up
```

### 3) Migrasyonlar

```bash
make migrate
```

### 4) Testler

```bash
make test
```

## MCP Endpoint

MCP endpointi `/mcp` altında çalışır. Bu servis `tool` + `arguments` ile JSON alır.

Örnek:

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "thread.create",
    "arguments": {}
  }'
```

### LibreChat MCP yapılandırması

LibreChat MCP URL’nizi şu şekilde ayarlayın:

- Uğur: `https://mcp.datasins.com/mcp`
- Gökçe: `https://mcp.gokce.ai/mcp`

## Plan Registry (Topic Separation)

Planlar ayrı çalışma konuları olarak yönetilir ve her thread bir plana bağlıdır.

### plan.create

```json
{
  "tool": "plan.create",
  "arguments": {
    "name": "memory-mcp-core",
    "meta": {"owner": "ugur"}
  }
}
```

### thread.create

```json
{
  "tool": "thread.create",
  "arguments": {
    "plan_id": "<plan_uuid>",
    "meta": {"topic": "ingest-pipeline"}
  }
}
```

## Örnek Tool Payloadları

### turn.ingest

```json
{
  "tool": "turn.ingest",
  "arguments": {
    "thread_id": "<uuid>",
    "role": "user",
    "text": "Yeni karar: Postgres kullanılacak.",
    "external_turn_id": "librechat-turn-123",
    "embed_now": true
  }
}
```

`external_turn_id` aynı değerle gelen tekrar çağrılarda idempotent davranır.

### distill.extract

```json
{
  "tool": "distill.extract",
  "arguments": {
    "thread_id": "<uuid>",
    "turn_id": "<uuid>",
    "include_recent_turns": 4,
    "write_to_memory": true
  }
}
```

### retrieve.context

```json
{
  "tool": "retrieve.context",
  "arguments": {
    "thread_id": "<uuid>",
    "query": "Hangi kararlar aktif?",
    "mode": "fast",
    "scope": "distilled_only",
    "top_k": 8,
    "token_budget": 800,
    "recency_bias": 0.1,
    "explain": true
  }
}
```

### audit.check_consistency

```json
{
  "tool": "audit.check_consistency",
  "arguments": {
    "thread_id": "<uuid>",
    "proposed_plan_text": "SQLite kullanalım.",
    "deep": true
  }
}
```

### shared.export

```json
{
  "tool": "shared.export",
  "arguments": {
    "thread_id": "<uuid>",
    "types": ["decision", "constraint"],
    "include_mistakes": false,
    "expires_in_minutes": 60
  }
}
```

### shared.import

```json
{
  "tool": "shared.import",
  "arguments": {
    "payload": {"...": "..."},
    "signature": "<hmac>"
  }
}
```

## Güvenlik

- Pydantic doğrulama + sıkı enumlar.
- Prompt injection güvenliği için sistem promptlarında açık uyarı.
- HMAC imza ile export/import.
- API anahtarları loglanmaz.

## Notlar

- `EMBEDDING_DIM` farklıysa migration güncellenmeli.
- `ENABLE_LLM_RERANK=true` ise low-confidence deep retrieval’da LLM rerank aktif olur.
- Retention politikaları `.env` içindeki `RETENTION_*` değişkenleriyle kontrol edilir.

## LibreChat Uçtan Uca Kullanım Örnekleri

### 1) Yeni Plan Başlatma

1. `plan.create` ile yeni plan oluşturun.
2. `thread.create` ile plan altında bir thread açın.
3. `turn.ingest` ile ilk kararları gönderin.

### 2) Mevcut Planı Devam Ettirme

1. `plan.list` ile planları bulun.
2. Mevcut planın thread ID’sini takip edin veya yeni thread ekleyin.
3. `distill.extract` ile yeni turn’lerden karar/kısıt çıkarın.

### 3) Deep Audit

1. `retrieve.context` ile `mode=deep` ve `explain=true` kullanın.
2. `audit.check_consistency` ile plan metnini doğrulatın.
3. `stale_references` çıktısını kontrol ederek superseded kararları güncelleyin.
