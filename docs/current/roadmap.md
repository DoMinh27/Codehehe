# Roadmap hiện hành

CodeHehe đã đủ chức năng cho một MVP trình diễn 1v1. Roadmap này chỉ liệt kê
những phần chưa triển khai; các ý tưởng đã hoàn thành không còn xuất hiện như
công việc tương lai.

## Ưu tiên 1 — độ tin cậy và khả năng chịu tải

- Tạo kịch bản load test cho Lobby, Battle polling, Submit, notification và
  presence; xác định giới hạn thực tế của Azure VM hiện tại
- Chuyển production từ SQLite sang PostgreSQL trước khi tăng số trận đồng thời
- Bổ sung theo dõi CPU, RAM, disk, HTTP 5xx, độ trễ và lịch sử downtime bằng
  Azure Monitor hoặc hệ thống quan sát tương đương
- Đưa queue, cache và presence sang Redis khi số ghi/poll thực tế vượt khả năng
  database hiện tại
- Đánh giá WebSocket chỉ cho dữ liệu cần realtime sau khi đã đo tải; không thay
  toàn bộ polling theo cảm tính

## Ưu tiên 2 — trải nghiệm cạnh tranh

- Thiết kế rating/Elo, leaderboard và mùa giải có chống farm giữa cùng cặp
- Bổ sung matchmaking tự động theo rating và trạng thái Sẵn sàng
- Thêm cooldown/draft/cân bằng Kỹ năng dựa trên telemetry trận, không chỉ cảm nhận
- Thêm rematch history và thống kê tác động Kỹ năng sau trận nếu dữ liệu đủ tin cậy

## Ưu tiên 3 — chế độ nhiều người

- Thiết kế Team identity, membership, role và invitation trên nền Notification
  Shell hiện có
- Thử nghiệm mode đội có vai trò hoặc tài nguyên chung, tránh chỉ cho nhiều người
  cùng giải một bộ bốn bài
- Sau khi mode đội ổn định mới xây tournament, check-in, bracket và team match
  invitation

## Ưu tiên 4 — nội dung và AI

- Mở rộng ngân hàng đề theo dữ liệu difficulty/topic và tỷ lệ AC thực tế
- Thêm cơ chế tránh lặp đề gần đây sau khi có đủ lịch sử
- Nâng độ ổn định AI Review bằng provider/model có SLA phù hợp, quota và fallback
- Chỉ mở rộng AI vào coaching/analytics khi đo được chi phí, chất lượng và giới
  hạn riêng tư; không để AI sinh code ảnh hưởng tính công bằng của trận

## Điều kiện trước khi mở rộng quy mô

- Backup/restore PostgreSQL được diễn tập
- Load test có ngưỡng p95 và tỷ lệ lỗi chấp nhận được
- Operations Dashboard và cảnh báo phản ánh đúng sự cố thực tế
- Không có hidden-test/source leak hoặc race tạo nhiều active match
- SMTP, Judge0, AI provider và certificate renewal đều có runbook kiểm tra
