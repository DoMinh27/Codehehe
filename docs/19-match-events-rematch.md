# MatchEvent, Timeline và Rematch

## Phạm vi

Timeline ghi lại các mốc quan trọng và hiển thị sau trận trong Result. Rematch
cho phép hai người của trận đã kết thúc mời nhau vào một phòng mới. Không thay
đổi luật tính điểm, chọn đề, Energy, Skill, Judge0 hoặc AI Review.

Không thêm live feed Battle, WebSocket, hệ thống event sourcing hay chế độ
nhiều người. Không ghi Run Code hoặc từng lần nộp sai vào timeline.

## Timeline

- `Match.timeline_version`: mặc định `0` với dữ liệu cũ; StartMatchService đặt
  thành `1` khi bắt đầu trận mới. Không backfill hoặc tạo timeline một phần cho
  trận đã bắt đầu trước migration.
- `MatchEvent`: match, kind, actor/target tùy chọn, snapshot tên người chơi,
  thời điểm ghi nhận, `event_key` và payload JSON allowlist.
- Unique `(match, event_key)` chống sự kiện trùng khi retry/idempotency replay.
  Event được ghi trong cùng transaction với thay đổi gameplay; lỗi ghi event
  làm rollback cả transaction, không để điểm/skill thay đổi mà thiếu event.
- Các loại event: `MATCH_STARTED`, `PROBLEM_SOLVED`, `FIRST_SOLVE_CONFIRMED`,
  `REWARD_GRANTED`, `SKILL_USED`, `TYPING_COMPLETED`, `PLAYER_SURRENDERED`,
  `MATCH_FINISHED`.
- `SKILL_USED` bao gồm kết quả Thanh tẩy/Steal; không sinh một event khác cho
  cùng thao tác. Reward ghi Energy thực tế sau giới hạn và skill được trao.
- First-solve chỉ ghi khi đã xác nhận theo logic submission đang có; kết quả
  Judge0 trả muộn không đảo thứ tự ghi nhận hoặc thay đổi trận đã FINISHED.
- Result hiển thị thứ tự ID tăng dần, thời gian tương đối từ lúc bắt đầu và
  phân trang 50 event bằng `?timeline_page=`. Thời gian ghi nhận có thể sau
  thời điểm hết giờ do chờ chấm/finalize; đây không phải replay theo thời gian
  người chơi gửi request.
- Snapshot giữ tên, bài, điểm, phần thưởng và kết quả trận tại lúc xảy ra.
  Không chứa code, hidden tests, reference solution, judge token/message,
  typing prompt, AI prompt hoặc API key. Template autoescape mọi nội dung.
- Participant và staff xem được Result như trước. Django Admin có danh sách
  event chỉ đọc và liên kết từ Match; không có API timeline mới.

## Rematch

Mỗi trận nguồn FINISHED có đúng hai participant được tạo tối đa một
`RematchRequest`. Staff không tham gia không được mời/đồng ý thay người chơi.

1. Một người bấm **Tái đấu**; tạo lời mời PENDING, hiệu lực 120 giây.
2. Đối thủ mở cùng Result để nhận lời mời và chọn **Đồng ý** hoặc **Từ chối**;
   người gửi có thể **Hủy lời mời**.
3. Đồng ý tạo atomically một Match WAITING mới và hai MatchPlayer. Người gửi
   là host; host bấm **Bắt đầu trận** theo luồng phòng chờ hiện có.
4. Phòng mới lấy cấu hình hiện tại; lúc Start chọn đề ngẫu nhiên như trận
   thường. Không sao chép điểm, code, inventory hay snapshot của trận trước;
   không bảo đảm bộ đề khác hoàn toàn trận trước.

Trước khi mời/đồng ý, cả hai phải còn active và không ở phòng/trận khác. Không
tự kéo người chơi khỏi phòng đang tham gia. Unique membership, transaction và
cơ chế retry SQLite bảo vệ request đồng thời; lỗi tạo người thứ hai rollback
cả phòng mới. Hai lời mời chéo chỉ trả về cùng một invitation, không tự đồng ý.

Status lưu trong DB: PENDING, ACCEPTED, DECLINED, CANCELLED. EXPIRED được suy
ra từ PENDING và expires_at khi đọc; GET không ghi DB, không cần timer mới.
Lời mời đã từ chối/hủy/hết hạn không mở lại trên cùng trận nguồn; người chơi
vẫn có thể tạo phòng thông thường. Retry thao tác đã thành công không tạo
invitation/phòng thứ hai.

### API và giao diện

- `GET /matches/<id>/rematch/state/`: trạng thái, server_time, expires_at,
  is_requester, requester_name, actions, room_url, new_match_status, terminal
  và unavailable_reason an toàn. `NONE` nghĩa là chưa có lời mời.
- `POST /matches/<id>/rematch/`: JSON `{"action": "request"}`; các action khác
  là accept, decline, cancel. Dùng session auth, CSRF và error envelope hiện có.
- Không lộ room khác đang khiến người chơi bận; không trả code hoặc dữ liệu AI.
  Result và các response rematch đều private/no-store.
- Poll 5 giây khi tab hiển thị, 30 giây khi ẩn, kể cả NONE để nhận lời mời.
  Dừng khi terminal; có nút **Cập nhật**. Request timeout 10 giây và không
  chồng request. Lỗi HTTP/network/non-JSON giữ dữ liệu gần nhất và cho thử lại.
- Tự vào phòng khi lời mời đang tương tác được đồng ý. Mở lại Result lịch sử
  đã ACCEPTED chỉ có liên kết tới phòng/trận/kết quả tái đấu, không tự chuyển
  trang. Script điều hướng active-match của base layout được tắt riêng Result.
- AI Review và Rematch khởi tạo độc lập; AI tắt hoặc lỗi cấu hình không ngăn
  Rematch hoạt động. UI dùng DOM API/textContent và native buttons.

## Migration và triển khai

- `matches.0021_match_event_timeline`: thêm version và bảng MatchEvent.
- `matches.0022_rematch_request`: bảng invitation và các constraint.
- Không thêm env, seed hoặc systemd unit. Timers hiện tại tiếp tục hoạt động.
- Trước production: backup SQLite và kiểm soát dịch vụ theo runbook deployment.
  Sau merge/pull: migrate, frontend build, collectstatic, restart Gunicorn.
  Không cần chạy lại seed_problems cho riêng tính năng này.
- Local: `python manage.py migrate`, `npm run build`, rồi chạy server hiện có.

## Nghiệm thu

- Tests tập trung: `python manage.py test matches.test_timeline matches.test_rematch`.
- Full: Django tests, Vitest, Ruff, system check, migration dry-run, build và
  `git diff --check`.
- Manual hai tài khoản: tạo trận mới; giải bài, dùng skill, kết thúc; xem đúng
  timeline; mời/đồng ý; xác nhận host và 2/2 người ở phòng mới; bắt đầu trận.
- Thử từ chối, hủy, chờ hết 120 giây, người chơi đang ở phòng khác, bấm lặp,
  mất mạng và mở lại Result lịch sử. Kiểm tra layout 1440/1024/390px, CSRF,
  permission, dữ liệu nhạy cảm và không tràn ngang ở component mới.
- Test tự động có migration từ schema cũ, rollback event/room, first-solve
  Judge0 trả lệch thứ tự, sáu skill, late verdict, permission, escape, pagination
  và race thực trên SQLite. Browser QA dùng database tạm, không sửa DB local.
