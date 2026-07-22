# TÀI LIỆU 1 — PROJECT CHARTER

**Tên file:** `00-project-charter.md`

## 1. Mục đích tài liệu

Project Charter chính thức khởi động dự án CodeHehe, xác định:

* Lý do dự án tồn tại.
* Mục tiêu cần đạt.
* Phạm vi V1.
* Các ràng buộc.
* Trách nhiệm của đội ngũ.
* Tiêu chí thành công.
* Nguyên tắc ra quyết định.
* Thẩm quyền quản lý thay đổi.

Mọi tài liệu, backlog, thiết kế kỹ thuật và hoạt động phát triển phải phù hợp với Project Charter này.

---

## 2. Tổng quan dự án

### 2.1. Tên sản phẩm

**CodeHehe**

Tên “Code Arena” từng xuất hiện trong tài liệu nháp và không còn được sử dụng. Tất cả tên hiển thị, repository, slide và tài liệu chính thức phải thống nhất sử dụng CodeHehe.

### 2.2. Loại sản phẩm

CodeHehe là nền tảng học và thi đấu lập trình 1v1 có yếu tố game hóa.

### 2.3. Người dùng mục tiêu

Người dùng chính:

* Sinh viên đang học lập trình.
* Người mới học Python.
* Người muốn luyện coding theo hình thức cạnh tranh trực tiếp.
* Người cảm thấy việc giải bài cá nhân trên các nền tảng truyền thống thiếu tương tác.

### 2.4. Bối cảnh thực hiện

Dự án được xây dựng để:

* Tham gia cuộc thi SOFTCON cấp trường.
* Tạo một sản phẩm phần mềm hoàn chỉnh.
* Public source code.
* Thuyết trình về sản phẩm, kiến trúc và quy trình phát triển.
* Chứng minh khả năng biến một ý tưởng game hóa giáo dục thành sản phẩm chạy được.

---

## 3. Vấn đề cần giải quyết

Các nền tảng luyện lập trình phổ biến chủ yếu tập trung vào:

* Giải bài cá nhân.
* Thi đấu thuật toán truyền thống.
* Bảng xếp hạng.
* Đánh giá kết quả sau khi nộp bài.

Trải nghiệm này có thể gây ra các vấn đề đối với người mới học:

* Thiếu tương tác trực tiếp.
* Thiếu cảm giác đang tham gia một trận đấu.
* Thiếu yếu tố chiến thuật.
* Khó duy trì động lực luyện tập.
* Hoạt động học dễ trở nên lặp lại và đơn điệu.

CodeHehe hướng tới việc biến quá trình giải bài lập trình thành một trận đấu cạnh tranh, trong đó năng lực coding vẫn là yếu tố cốt lõi nhưng được bổ sung bằng cơ chế Energy, Skills, Defense và Minigames ở các phiên bản tiếp theo.

---

## 4. Tầm nhìn sản phẩm

CodeHehe hướng tới mô hình:

```text
Coding Challenge
+ 1v1 Competition
+ Energy
+ Skills
+ Defense
+ Minigames
+ Elo
+ Rank
```

Coding là nền tảng chính. Các yếu tố game hóa phải tạo thêm chiến thuật và động lực, nhưng không được biến kết quả trận đấu thành trò may rủi không phụ thuộc năng lực lập trình.

---

## 5. Mục tiêu V1

V1 tập trung xây dựng **Coding Battle Core**.

Hệ thống phải cho phép:

1. Người dùng đăng ký và đăng nhập.
2. Admin quản lý ngân hàng đề.
3. Một người chơi tạo phòng bằng mã.
4. Người chơi thứ hai tham gia bằng mã phòng.
5. Host bắt đầu trận khi đủ hai người.
6. Hai người nhận cùng danh sách bài đã được cố định.
7. Hai người giải bài theo tiến trình độc lập.
8. Người chơi submit code Python.
9. Judge0 chấm code bằng hidden tests.
10. Hệ thống lưu Submission và verdict.
11. Hệ thống cộng điểm đúng một lần cho mỗi bài.
12. Người giải bài trước nhận First-solve bonus.
13. Điểm và tiến độ đối thủ được cập nhật gần thời gian thực.
14. Timer do server kiểm soát.
15. Hệ thống xác định và lưu kết quả trận.
16. Người chơi có thể refresh và quay lại trận đang diễn ra.

---

## 6. Mục tiêu dài hạn

### V1.5 — Energy Core

* Giải một bài nhận 1 Energy.
* Energy tối đa 3.
* Một Hint tiêu hao 1 Energy.

### V2 — Skill Battle

* Attack Skills.
* Skill inventory.
* Energy cost.
* Active effects.
* Skill usage history.

### V2.5 — Defensive Skills

* Cleanse.
* Reflect.
* Shield.

### V3 — Minigames

* Gõ đúng chuỗi.
* Giải toán.
* Flappy Bird.
* Dinosaur game.

### V4 — Competitive System

* Elo.
* Rank.
* Leaderboard.
* Match history.
* Automatic matchmaking.
* PostgreSQL.
* Redis và WebSocket nếu có nhu cầu thực tế.

---

## 7. Phạm vi V1

### 7.1. Trong phạm vi

* Django monolith.
* Django Templates.
* Django Auth và Session.
* Django Admin.
* SQLite.
* Vanilla JavaScript.
* Polling.
* Judge0.
* Python only.
* Problem Bank.
* Sample tests.
* Hidden tests.
* Room code.
* Match 1v1.
* Frozen MatchProblem.
* Submission.
* Verdict.
* Base score.
* First-solve bonus `+1`.
* Server timer.
* Match state endpoint.
* Result.
* Refresh và quay lại trận.
* Deployment lên môi trường cloud.
* Demo và tài liệu bảo vệ.

### 7.2. Ngoài phạm vi V1

* Energy.
* Hint sử dụng Energy.
* Attack Skills.
* Defensive Skills.
* Minigames.
* Elo.
* Rank.
* Leaderboard.
* Automatic matchmaking.
* Tournament.
* Team battle.
* Spectator.
* Chat.
* Economy.
* Multiple programming languages.
* React.
* FastAPI.
* WebSocket.
* Redis.
* PostgreSQL trong baseline ban đầu.
* Microservices.
* Celery.
* RabbitMQ.
* Kubernetes.
* Custom admin interface.
* Mobile application.

Các tính năng ngoài phạm vi không bị loại bỏ khỏi Product Vision. Chúng chỉ không được phép làm chậm Coding Battle Core.

---

## 8. Kiến trúc V1 được phê duyệt

```text
Browser
   │
   ├── Django Templates
   ├── HTML/CSS
   └── Vanilla JavaScript polling
            │
            ▼
         Django
   ├── accounts
   ├── problems
   ├── matches
   ├── submissions
   ├── gameplay
   ├── Django Auth
   └── Django Admin
       │              │
       ▼              ▼
    SQLite          Judge0
```

### Stack chính thức

* Backend: Django 5.2 LTS.
* Frontend: Django Templates.
* JavaScript: Vanilla JavaScript.
* Database V1: SQLite.
* ORM: Django ORM.
* Authentication: Django Auth và Session.
* Admin: Django Admin.
* Cập nhật trạng thái: Polling.
* Chạy code: Judge0 qua external endpoint trước.
* Submission language: Python.
* Runtime chính thức: Python 3.12.
* Source control: GitHub.
* Cloud credit: Azure for Students, 100 USD trong 12 tháng.

---

## 9. Đội ngũ và trách nhiệm

### Thành viên A — Backend và Database

Chịu trách nhiệm chính:

* Django Models.
* Migrations.
* Auth.
* Problem Bank.
* Django Admin.
* Match.
* Room.
* Database constraints.
* Server-side validation.

### Thành viên B — Frontend và UX

Chịu trách nhiệm chính:

* User Flow.
* Wireframe.
* Django Templates.
* HTML/CSS.
* Lobby.
* Waiting Room.
* Battle UI.
* Polling.
* Loading, error và disabled states.
* Result page.

### Thành viên C — Judge và Gameplay

Chịu trách nhiệm chính:

* JudgeService interface.
* FakeJudgeService.
* Judge0 integration.
* SubmissionService.
* Verdict mapping.
* Hidden test execution.
* ScoringService.
* First-solve.
* Timer và winner logic.
* Automated tests.

### Trách nhiệm chung

Cả ba thành viên phải hiểu được flow:

```text
Submit
→ Django View
→ SubmissionService
→ JudgeService
→ Judge0
→ lưu Submission
→ ScoringService
→ cập nhật MatchPlayer
→ frontend lấy Match State
```

Không được tồn tại module mà chỉ Codex hoặc một thành viên duy nhất hiểu.

---

## 10. Ràng buộc dự án

### 10.1. Thời gian

* Tổng thời gian: 4 tuần.
* Judge0 phải được tích hợp trong Tuần 2.
* Playable MVP phải hoàn thành cuối Tuần 3.
* Giữa Tuần 4 thực hiện feature freeze.
* Cuối Tuần 4 phải có final release và demo ổn định.

### 10.2. Năng lực đội ngũ

* Đội mạnh về Python cơ bản.
* Có kiến thức ML/DL cơ bản.
* Kiến thức web, database và deployment còn hạn chế.
* Kiến trúc phải đủ đơn giản để học và kiểm soát trong bốn tuần.

### 10.3. Công nghệ

Không tự ý thêm:

* Redis.
* WebSocket.
* React.
* FastAPI.
* PostgreSQL.
* Docker bắt buộc.
* WSL bắt buộc.
* Node.js.
* Microservices.

Mọi dependency mới phải có lý do, được review và ghi vào Decision Log.

### 10.4. Codex

* Codex chỉ thực hiện task nhỏ.
* Prompt phải có scope và acceptance criteria.
* Không prompt Codex xây toàn bộ hệ thống.
* Không merge code không giải thích được.
* Codex không có quyền thay đổi Product Requirements hoặc Gameplay Rules.

---

## 11. Tiêu chí thành công

V1 được coi là thành công khi:

```text
Register
→ Login
→ Admin tạo Problem/TestCase
→ Player A tạo phòng
→ Player B join
→ Host start
→ Cả hai nhận cùng danh sách bài
→ Submit Python
→ Judge0 chấm hidden tests
→ Lưu Submission
→ Cộng điểm
→ First-solve +1
→ Polling cập nhật trạng thái
→ Timer kết thúc
→ Winner đúng
→ Result
```

Ngoài việc chạy được, nhóm phải:

* Giải thích được kiến trúc.
* Giải thích được database.
* Giải thích được Judge0.
* Giải thích được hidden tests.
* Giải thích được timer.
* Giải thích được First-solve.
* Giải thích được lý do chọn Django.
* Trình bày được roadmap Energy và Skills.
* Demo lặp lại được nhiều lần.
* Có video dự phòng.

---

## 12. Nguyên tắc quản trị

* `main` phải luôn chạy được.
* Không push trực tiếp vào `main`.
* Mỗi task có một owner.
* Mỗi pull request có ít nhất một reviewer.
* Task phải có acceptance criteria.
* Thay đổi scope phải ghi Decision Log.
* Milestone phải được kiểm tra bằng demo, không bằng phần trăm cảm tính.
* Không báo cáo “đã làm 80%” nếu chưa có output chạy được.
* Ưu tiên hoàn thành flow end-to-end hơn số lượng tính năng.


```text
docs/
├── 00-project-charter.md        (tài liệu này)
├── 02-prd-v1.md                 Product Requirements V1
├── 03-gameplay-rules-v1.md      Gameplay Rules V1
├── 04-roadmap-v1.md             Roadmap 4 tuần
├── 15-decision-log.md           Decision Log
└── (System Design, Database Design, Interface Contract — viết tiếp sau charter này)
```
