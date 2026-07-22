# TÀI LIỆU 2 — PRODUCT REQUIREMENTS DOCUMENT

**Tên file:** `02-prd-v1.md`

## 1. Mục đích

PRD mô tả những gì CodeHehe V1 phải thực hiện từ góc nhìn sản phẩm.

PRD không quy định chi tiết code, nhưng là căn cứ để:

* Viết System Design.
* Thiết kế database.
* Viết backlog.
* Viết acceptance criteria.
* Kiểm thử.
* Xác định MVP hoàn thành.

---

## 2. Product Statement

CodeHehe là nền tảng thi đấu lập trình 1v1 dành cho sinh viên và người mới học Python. Hai người chơi giải cùng một danh sách bài trong thời gian giới hạn, submit code để chấm tự động và theo dõi tiến độ của nhau gần thời gian thực.

V1 xây dựng nền tảng Coding Battle Core. Các phiên bản sau bổ sung Energy, Skills, Defense, Minigames và Elo.

---

## 3. User Roles

## 3.1. Player

Player có thể:

* Đăng ký.
* Đăng nhập.
* Đăng xuất.
* Tạo phòng.
* Join phòng.
* Bắt đầu trận nếu là host.
* Xem đề bài.
* Submit code.
* Xem verdict.
* Xem điểm và tiến độ trận.
* Xem kết quả.

## 3.2. Admin

Admin có thể:

* Đăng nhập Django Admin.
* Tạo, sửa và vô hiệu hóa Problem.
* Thêm sample tests.
* Thêm hidden tests.
* Cấu hình độ khó.
* Cấu hình điểm.
* Kiểm tra Submission khi cần.

---

## 4. User Flow chính

```text
Đăng ký
→ Đăng nhập
→ Lobby
→ Tạo phòng hoặc nhập mã phòng
→ Waiting Room
→ Host bắt đầu trận
→ Battle
→ Submit code
→ Nhận verdict và điểm
→ Theo dõi đối thủ
→ Hết thời gian
→ Result
```

---

## 5. Functional Requirements

## Nhóm A — Authentication

### FR-AUTH-01 — Đăng ký

Người dùng có thể tạo tài khoản với:

* Username.
* Password.
* Password confirmation.

Acceptance criteria:

* Username không được trùng.
* Password phải được hash bằng cơ chế Django.
* Đăng ký thành công chuyển người dùng tới trang Login hoặc tự đăng nhập theo quyết định UI.
* Input không hợp lệ phải có thông báo.

### FR-AUTH-02 — Đăng nhập

* Người dùng đăng nhập bằng username và password.
* Hệ thống tạo Django Session.
* Người dùng đăng nhập thành công được chuyển đến Lobby.

### FR-AUTH-03 — Đăng xuất

* Người dùng có thể đăng xuất.
* Session bị kết thúc.
* Trang yêu cầu authentication không còn truy cập được.

### FR-AUTH-04 — Route protection

Các trang sau yêu cầu đăng nhập:

* Lobby.
* Create Room.
* Join Room.
* Waiting Room.
* Battle.
* Result của trận thuộc người dùng.

---

## Nhóm B — Problem Bank

### FR-PROB-01 — Tạo Problem

Admin có thể tạo Problem gồm:

* Title.
* Statement.
* Difficulty.
* Points.
* Starter code.
* Order.
* Active status.

### FR-PROB-02 — TestCase

Admin có thể thêm nhiều TestCase cho mỗi Problem.

Mỗi TestCase gồm:

* Input.
* Expected output.
* Sample/hidden status.
* Order.

### FR-PROB-03 — Hiển thị Problem

Player có thể xem:

* Title.
* Statement.
* Difficulty.
* Points.
* Starter code.
* Sample tests.

### FR-PROB-04 — Bảo vệ hidden tests

Hidden tests:

* Không xuất hiện trong HTML.
* Không xuất hiện trong JSON response.
* Không được gửi tới browser.
* Chỉ SubmissionService và JudgeService được truy cập.

### FR-PROB-05 — Active status

Problem bị vô hiệu hóa:

* Không được chọn cho trận mới.
* Không được xóa dữ liệu lịch sử của trận cũ.

---

## Nhóm C — Room

### FR-ROOM-01 — Tạo phòng

Player đã đăng nhập có thể tạo phòng.

Hệ thống:

* Tạo Match trạng thái `WAITING`.
* Tạo MatchPlayer cho host.
* Sinh mã phòng 6 ký tự.
* Mã sử dụng chữ in hoa và chữ số.
* Mã không trùng với phòng đang hoạt động.

### FR-ROOM-02 — Join phòng

Player có thể nhập room code để tham gia.

Backend phải kiểm tra:

* Room tồn tại.
* Room đang `WAITING`.
* Room chưa đủ hai người.
* Player chưa có mặt trong room.
* Player không phải host của cùng room dưới record khác.

### FR-ROOM-03 — Giới hạn người chơi

* Mỗi Match có tối đa hai MatchPlayer.
* Người thứ ba bị từ chối.
* Phải có thông báo “Phòng đã đầy”.

### FR-ROOM-04 — Host

* Người tạo phòng là host.
* Chỉ host được phép bắt đầu trận trong V1.

### FR-ROOM-05 — Waiting Room

Waiting Room hiển thị:

* Room code.
* Host.
* Người chơi thứ hai.
* Trạng thái chờ.
* Nút Start dành cho host.
* Thông báo chưa đủ người.

Waiting Room có thể sử dụng polling khoảng hai giây để cập nhật người chơi thứ hai.

---

## Nhóm D — Match

### FR-MATCH-01 — Bắt đầu trận

Host chỉ có thể bắt đầu khi:

* Match đang `WAITING`.
* Có đúng hai người.
* Chưa có `started_at`.

### FR-MATCH-02 — Frozen Problem List

Khi trận bắt đầu:

* Server chọn đúng 4 Problem.
* Tạo 4 MatchProblem.
* Thứ tự Problem được cố định.
* Hai người nhận cùng MatchProblem.
* Danh sách không thay đổi trong trận.

Cách chọn V1:

* Chọn 4 Problem active theo bộ đề đã được Admin cấu hình và sắp thứ tự.
* Không sử dụng random phức tạp trong V1.
* Hai bài đầu là Easy.
* Hai bài sau là Medium.
* V1 không bắt buộc dùng bài Hard.

### FR-MATCH-03 — Tiến trình độc lập

* Hai người cùng thấy danh sách bài.
* Mỗi người tự chọn bài để giải.
* Việc một người giải xong không làm thay đổi bài của đối thủ.
* Không bắt buộc giải tuần tự.

### FR-MATCH-04 — Thời lượng

* Một trận kéo dài 15 phút.
* Server lưu `started_at` và `ends_at`, hoặc `duration_seconds = 900`.
* Frontend countdown dựa trên thời gian server.
* Refresh không reset timer.

### FR-MATCH-05 — Trạng thái Match

Các trạng thái:

```text
WAITING
PLAYING
FINISHED
CANCELLED
```

### FR-MATCH-06 — Refresh và quay lại

* Player refresh trang được quay lại trận.
* Player đăng nhập lại có thể mở trận đang `PLAYING`.
* Disconnect không tạm dừng timer.
* Không cần WebSocket reconnect trong V1.

### FR-MATCH-07 — Kết thúc trận

Match kết thúc khi:

* Timer hết; hoặc
* Cả hai Player đã giải toàn bộ 4 bài.

Nếu chỉ một Player giải hết bài, trận vẫn tiếp tục để Player còn lại có cơ hội thi đấu đến hết thời gian.

---

## Nhóm E — Submission và Judge

### FR-SUB-01 — Submit code

Player gửi:

* Source code.
* MatchProblem hoặc Problem ID tương ứng.

Frontend không gửi:

* Verdict.
* Score.
* Accepted status.
* First-solve status.
* Hidden tests.

### FR-SUB-02 — Kiểm tra trước khi chấm

Backend phải kiểm tra:

* Player đã đăng nhập.
* Player thuộc Match.
* Match đang `PLAYING`.
* Problem thuộc Match.
* Source code không rỗng.
* Submission được server tiếp nhận không muộn hơn `ends_at`.

### FR-SUB-03 — Judge0

* Backend gửi source code và hidden tests tới Judge0.
* V1 dùng Judge0 external endpoint trước, cấu hình qua biến môi trường.
* Judge0 chạy code trong sandbox.
* Django không chạy code trực tiếp.
* Không dùng `exec()` hoặc `eval()`.

### FR-SUB-04 — Verdict

Hệ thống chuẩn hóa verdict thành:

```text
PENDING
ACCEPTED
WRONG_ANSWER
COMPILATION_ERROR
RUNTIME_ERROR
TIME_LIMIT_EXCEEDED
INTERNAL_ERROR
```

### FR-SUB-05 — Submission trước giờ hết

Nếu Submission được server tiếp nhận trước hoặc đúng `ends_at`:

* Submission vẫn được chấm.
* Kết quả vẫn được tính dù Judge0 hoàn thành sau `ends_at`.

Nếu Submission được tiếp nhận sau `ends_at`:

* Backend từ chối.
* Không gửi Judge0.
* Không tính điểm.

### FR-SUB-06 — Judge error

Nếu Judge0 lỗi:

* Submission nhận `INTERNAL_ERROR` hoặc trạng thái tương đương.
* Không cộng điểm.
* Player có thể submit lại nếu trận còn thời gian.
* UI hiển thị thông báo kiểm soát được.

---

## Nhóm F — Scoring

### FR-SCORE-01 — Base score

Điểm mặc định:

* Easy: 1 điểm.
* Medium: 2 điểm.
* Hard: 3 điểm.

Admin có thể cấu hình `points` cho từng Problem.

MatchProblem phải snapshot điểm tại thời điểm bắt đầu trận để việc sửa Problem sau đó không làm thay đổi điểm trận.

### FR-SCORE-02 — Accepted lần đầu

* Player chỉ nhận base score khi Accepted bài lần đầu.
* Accepted lại bài đã giải không cộng thêm điểm.
* Wrong Answer và các lỗi khác không cộng điểm.
* Không trừ điểm khi submit sai trong V1.

### FR-SCORE-03 — First-solve

* Người Accepted một bài trước đối thủ nhận thêm 1 điểm.
* Mỗi MatchProblem chỉ có một First-solver.
* Thứ tự First-solve dựa trên `received_at`.
* Không dựa trên thời điểm Judge0 hoàn thành.
* Backend phải xử lý trường hợp submission đến trước nhưng hoàn thành sau.
* First-solve phải được xử lý idempotent.
* Không được cộng First-solve cho cả hai người.

### FR-SCORE-04 — Winner

Thứ tự xác định kết quả:

1. Người có tổng điểm cao hơn thắng.
2. Nếu bằng điểm, trận hòa.

### FR-SCORE-05 — Server authority

* Score được tính hoàn toàn ở backend.
* Frontend chỉ hiển thị.
* Player không được gửi score.
* MatchPlayer.score phải khớp với tổng điểm đã awarded.

---

## Nhóm G — Match State và Polling

### FR-STATE-01 — State endpoint

```text
GET /matches/<match_id>/state/
```

Response tối thiểu:

```json
{
  "status": "PLAYING",
  "server_time": "ISO-8601 timestamp",
  "remaining_seconds": 438,
  "my_score": 3,
  "opponent_score": 2,
  "my_solved_problem_ids": [1, 2],
  "opponent_solved_problem_ids": [1],
  "winner_id": null
}
```

### FR-STATE-02 — Tần suất

* Battle: khoảng một giây.
* Waiting Room: khoảng hai giây.
* Tab bị ẩn: giảm còn khoảng 3–5 giây nếu kịp triển khai.
* Match Finished: dừng polling.

### FR-STATE-03 — Hiệu năng

State endpoint:

* Không gọi Judge0.
* Không write database.
* Không trả source code.
* Không trả hidden tests.
* Không trả toàn bộ Submission history.
* Không tạo N+1 query.
* Mục tiêu khoảng 3–6 query cố định/request.

---

## Nhóm H — Result

### FR-RESULT-01 — Kết quả

Result page hiển thị:

* Winner hoặc Draw.
* Điểm của hai Player.
* Số bài đã giải.
* First-solve của từng bài nếu cần.
* Thời gian kết thúc.

### FR-RESULT-02 — Quyền truy cập

* Chỉ người thuộc Match hoặc Admin được xem.
* Không cần spectator trong V1.

---

## 6. Non-functional Requirements

### NFR-01 — Security

* Không commit `.env`.
* Không lộ Django secret key.
* Không lộ hidden tests.
* Không dùng `exec()` hoặc `eval()`.
* Django CSRF phải hoạt động đối với request thay đổi dữ liệu.
* Route phải kiểm tra quyền ở backend.

### NFR-02 — Reliability

* Refresh không làm mất Match.
* Duplicate request không được cộng điểm hai lần.
* Judge lỗi không làm crash Django.
* Trạng thái Match phải lưu trong database.

### NFR-03 — Performance

Mục tiêu demo:

* Hỗ trợ một số trận đồng thời.
* Polling không gây N+1.
* State response nhỏ.
* Không cần tối ưu cho hàng nghìn người trong V1.

### NFR-04 — Maintainability

* Business logic không đặt toàn bộ trong View.
* Judge0 nằm sau JudgeService.
* Scoring nằm trong ScoringService.
* Model có constraint.
* Code được chia theo Django app.
* Tên biến, class và function dùng tiếng Anh.

### NFR-05 — Explainability

* Cả ba thành viên phải giải thích được flow chính.
* Mọi pull request phải có hướng dẫn test.
* Không merge code mà owner không hiểu.

### NFR-06 — Deployment

* Có URL demo.
* Có health endpoint.
* Có seed data.
* Có admin account.
* Có video dự phòng.
* Azure credit phải được kiểm soát.

---

## 7. MVP Acceptance Criteria

MVP chỉ được xác nhận Done khi toàn bộ flow sau chạy được:

```text
Player A đăng ký và đăng nhập
→ Player A tạo phòng
→ Player B đăng nhập và join
→ Host start
→ Server tạo 4 MatchProblem
→ Hai người thấy cùng 4 bài
→ Player A submit code đúng
→ Judge0 trả Accepted
→ Base score + First-solve được cộng
→ Player B thấy điểm cập nhật
→ Player B submit
→ Điểm được cập nhật đúng
→ Timer hết
→ Match chuyển FINISHED
→ Winner được xác định
→ Result hiển thị đúng
```

---
