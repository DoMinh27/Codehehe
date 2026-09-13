# Kiến trúc CodeHehe hiện tại

## Tổng quan

```text
Browser
  ├─ Django templates + frontend bundle
  ├─ HTTP polling cho Battle, notification, presence và dashboard
  └─ POST có CSRF cho gameplay, auth và social actions
          │
       Nginx
          │
       Gunicorn / Django 5.2
          ├─ SQLite
          ├─ Judge0 REST API
          ├─ AI provider API
          └─ SMTP provider

systemd timers
  ├─ Match Sweeper
  ├─ AI Review Processor
  └─ Pending Registration Cleanup
```

Production hiện đặt Nginx, Django, SQLite và Judge0 trên cùng Azure VM. Nginx
chỉ công khai HTTP/HTTPS; Gunicorn và Judge0 được giữ sau loopback hoặc reverse
proxy. Local có thể dùng Judge0 cùng máy hoặc endpoint tương thích bên ngoài.

## Các app

- `accounts`: đăng ký chờ, email đã xác minh, password recovery, profile và ngày
  hoạt động
- `problems`: ngân hàng đề, test case, metadata nguồn, seed JSON và Judge0 adapter
- `matches`: phòng/trận, snapshot luật/đề/Kỹ năng, submission, scoring, AI Review,
  Timeline, Rematch và Fair Play
- `social`: friendship, block, presence, notification projection và direct match
  invitation
- `operations`: heartbeat worker, health check, aggregate và Dashboard V2
- `config`: settings, URL gốc, health và readiness

Business rule nằm trong service modules; view xử lý HTTP và ủy quyền cho service.
Mọi dữ liệu có thể thay đổi trong lúc trận diễn ra như đề, luật và Kỹ năng được
snapshot để trận đang chơi không đổi theo cấu hình global.

## Dữ liệu và tính nhất quán

- SQLite dùng timeout cấu hình và transaction/row locking theo khả năng backend
- Constraint bảo đảm mỗi user chỉ có một `MatchPlayer` active và mỗi phòng chỉ
  có hai slot hợp lệ
- Submission, scoring, reward, SkillUse và MatchEvent dùng idempotency hoặc khóa
  transaction để tránh tiêu hao/ghi điểm lặp
- `MatchEvent` là audit timeline, không phải event store để tái tạo toàn bộ trận
- Notification không có bảng tổng quát; server tạo projection từ Rematch,
  FriendRequest và DirectMatchInvitation
- Password chưa xác minh chỉ tồn tại dưới dạng hash trong `PendingRegistration`;
  `User` và `AccountEmail` chỉ được tạo atomically sau xác minh

## Tác vụ nền và dịch vụ ngoài

- Match Sweeper kết thúc trận quá hạn và phục hồi submission bị kẹt
- AI Review Processor xử lý queue nhận xét sau trận; hỗ trợ Groq, Gemini và
  OpenRouter qua cấu hình
- Account Cleanup xóa đăng ký chờ đã quá thời gian giữ lại
- Worker cập nhật `WorkerHeartbeat` để Operations Dashboard phát hiện stale hoặc
  failure
- SMTP gửi email xác minh và đặt lại mật khẩu; local mặc định in email ra console

## Frontend và bảo mật

- JavaScript được build bằng npm/Vite và Django phục vụ bundle qua static files
- Không dùng React, WebSocket, SSE hoặc Redis ở phiên bản hiện tại
- Payload Battle theo người xem, không trả Khiên/Thanh tẩy riêng tư của đối thủ
- Source chỉ chủ sở hữu được xem; Result/Timeline giữ quyền participant/staff
- Hidden tests, reference solution, Judge0 token/message, API key, prompt/result
  AI và clipboard content không được đưa vào payload người chơi
- Các endpoint nhạy cảm dùng session auth, CSRF và `Cache-Control: private,
  no-store`

## Hướng nâng tải

Thứ tự nâng cấp khuyến nghị là PostgreSQL, đo tải/quan sát lỗi, Redis cho cache,
presence và queue, sau đó mới đánh giá WebSocket cho các màn hình thực sự cần
realtime. API hiện tại nên được giữ tương thích để có thể thay backend theo từng
bước thay vì viết lại toàn hệ thống.
