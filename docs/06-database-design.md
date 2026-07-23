# TÀI LIỆU 6 — DATABASE DESIGN V1

**Tên file:** `06-database-design.md`

## 1. Mục đích

Tài liệu này chốt database design cho CodeHehe V1 trước khi dựng Django models và migrations.

Database V1 phải phục vụ luồng:

```text
User đăng nhập
→ tạo/join phòng
→ start match
→ snapshot 4 bài
→ submit code
→ Judge0 trả verdict
→ tính score và first-solve
→ polling state
→ result
```

Thiết kế ưu tiên:

* Dễ hiểu với nhóm.
* Dễ hiện thực bằng Django ORM.
* Có constraint để tránh cộng điểm trùng.
* Không làm state endpoint phải write database.
* Chuẩn bị đường nâng cấp Energy, Skills, Elo sau V1 mà không làm V1 phức tạp.

---

## 2. Công nghệ database

* Database V1: SQLite.
* ORM: Django ORM.
* Auth: Django built-in `User`.
* Primary key: dùng `BigAutoField` mặc định của Django.
* Timezone: bật `USE_TZ = True`.
* Thời gian lưu bằng `DateTimeField`.

SQLite đủ cho demo nhỏ, nhưng cần giữ transaction ngắn và tránh write trong polling để giảm nguy cơ `database is locked`.

---

## 3. ERD tổng quan

```text
User
  │
  ├── Match.host
  │
  └── MatchPlayer.user
          │
          ├── Submission.player
          └── PlayerProblemProgress.player

Problem
  │
  ├── TestCase.problem
  └── MatchProblem.problem
          │
          ├── Submission.match_problem
          ├── PlayerProblemProgress.match_problem
          └── MatchProblem.first_solver

Match
  │
  ├── MatchPlayer.match
  ├── MatchProblem.match
  └── Submission.match
```

---

## 4. Model: User

### Nguồn

Dùng `django.contrib.auth.models.User`.

### Mục đích

Lưu tài khoản Player và Admin.

### Ghi chú V1

* Không tạo custom user trong V1.
* Admin dùng Django Admin.
* Player dùng username/password.
* Profile, avatar, Elo, rank để sau V1.

---

## 5. Model: Problem

### App đề xuất

`problems`

### Mục đích

Lưu đề bài trong ngân hàng đề.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `title` | `CharField(max_length=200)` | Có | Tên bài |
| `statement` | `TextField` | Có | Nội dung đề |
| `difficulty` | `CharField(choices)` | Có | `EASY`, `MEDIUM`, `HARD` |
| `points` | `PositiveIntegerField` | Có | Điểm gốc |
| `starter_code` | `TextField(blank=True)` | Không | Code mẫu ban đầu |
| `order` | `PositiveIntegerField(default=0)` | Có | Thứ tự chọn bài V1 |
| `is_active` | `BooleanField(default=True)` | Có | Chỉ bài active được chọn cho match mới |
| `created_at` | `DateTimeField(auto_now_add=True)` | Có | Audit |
| `updated_at` | `DateTimeField(auto_now=True)` | Có | Audit |

### Choices

```text
EASY
MEDIUM
HARD
```

### Constraints và indexes

* Index: `is_active`, `difficulty`, `order`.
* `points >= 1`.

### Ghi chú V1

* V1 chọn 4 bài active theo cấu hình và `order`.
* Mặc định match gồm 2 Easy + 2 Medium.
* Không hard-delete Problem đã từng dùng trong Match.
* Khi start match, điểm, title, statement, starter code và difficulty được snapshot sang `MatchProblem`.
* V1 không snapshot TestCase. Admin không được sửa TestCase của Problem đang dùng trong Match `PLAYING`.

---

## 6. Model: TestCase

### App đề xuất

`problems`

### Mục đích

Lưu sample tests và hidden tests cho mỗi Problem.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `problem` | `ForeignKey(Problem, related_name="test_cases")` | Có | Bài thuộc về |
| `input_data` | `TextField(blank=True)` | Không | Input truyền cho Judge0 |
| `expected_output` | `TextField` | Có | Output kỳ vọng |
| `is_sample` | `BooleanField(default=False)` | Có | Sample được hiển thị cho Player |
| `order` | `PositiveIntegerField(default=0)` | Có | Thứ tự hiển thị/chấm |
| `created_at` | `DateTimeField(auto_now_add=True)` | Có | Audit |

### Constraints và indexes

* Index: `problem`, `is_sample`, `order`.
* Không yêu cầu unique `order`, để admin dễ nhập trước; có thể siết lại sau nếu cần.

### Ghi chú V1

* Sample tests có thể xuất hiện trong HTML/JSON.
* Hidden tests không bao giờ gửi về browser.
* `SubmissionService` và `JudgeService` là nơi được đọc hidden tests.

---

## 7. Model: Match

### App đề xuất

`matches`

### Mục đích

Lưu một trận đấu 1v1.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `room_code` | `CharField(max_length=6, unique=True)` | Có | Mã phòng 6 ký tự |
| `host` | `ForeignKey(User, related_name="hosted_matches")` | Có | Người tạo phòng |
| `status` | `CharField(choices, default="WAITING")` | Có | Trạng thái match |
| `started_at` | `DateTimeField(null=True, blank=True)` | Không | Thời điểm start |
| `ended_at` | `DateTimeField(null=True, blank=True)` | Không | Thời điểm kết thúc |
| `duration_seconds` | `PositiveIntegerField(default=900)` | Có | 15 phút |
| `winner` | `ForeignKey(User, null=True, blank=True, related_name="won_matches")` | Không | Null nếu chưa xong hoặc Draw |
| `is_draw` | `BooleanField(default=False)` | Có | True nếu hòa |
| `created_at` | `DateTimeField(auto_now_add=True)` | Có | Audit |
| `updated_at` | `DateTimeField(auto_now=True)` | Có | Audit |

### Choices

```text
WAITING
PLAYING
FINISHED
CANCELLED
```

### Derived values

`ends_at` không bắt buộc lưu field riêng. Có thể tính:

```text
started_at + duration_seconds
```

Nếu khi implement thấy dùng nhiều, có thể thêm `ended_at` vẫn là thời điểm thực sự kết thúc, còn `ends_at` là property.

### Constraints và indexes

* Unique: `room_code`.
* Index: `status`, `room_code`, `created_at`.
* `duration_seconds > 0`.
* Không cho phép đồng thời có `winner != null` và `is_draw = true`.
* Nếu `status = PLAYING` thì `started_at` không được null. Rule này có thể enforce trong service thay vì DB constraint để đơn giản.

### CheckConstraint đề xuất

```python
CheckConstraint(
    check=~(Q(winner__isnull=False) & Q(is_draw=True)),
    name="match_winner_or_draw_not_both",
)
```

### Ghi chú V1

* Mỗi Match tối đa 2 Player qua `MatchPlayer`.
* `winner = null` và `is_draw = true` nghĩa là Draw.
* `winner = null` và `is_draw = false` nghĩa là chưa có winner hoặc match bị cancel.

---

## 8. Model: MatchPlayer

### App đề xuất

`matches`

### Mục đích

Liên kết User với Match và lưu score hiện tại.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `match` | `ForeignKey(Match, related_name="players")` | Có | Trận |
| `user` | `ForeignKey(User, related_name="match_players")` | Có | Người chơi |
| `score` | `IntegerField(default=0)` | Có | Điểm hiện tại |
| `joined_at` | `DateTimeField(auto_now_add=True)` | Có | Thời điểm join |
| `is_host` | `BooleanField(default=False)` | Có | Host flag |

### Constraints và indexes

* Unique: `(match, user)`.
* Index: `match`, `user`.
* `score >= 0`.

### Rule service cần enforce

* Một Match chỉ có tối đa 2 MatchPlayer.
* Chỉ host được start match.
* Không cho người thứ ba join.

### Ghi chú mở rộng

Sau V1 có thể thêm:

* `energy`.
* `shield`.
* `effects`.
* Elo snapshot.

---

## 9. Model: MatchProblem

### App đề xuất

`matches`

### Mục đích

Snapshot bài trong một Match. Đây là lớp chống việc admin sửa Problem làm thay đổi trận đang/chưa xem lại.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `match` | `ForeignKey(Match, related_name="match_problems")` | Có | Trận |
| `problem` | `ForeignKey(Problem, related_name="match_problems")` | Có | Problem gốc |
| `order` | `PositiveIntegerField` | Có | Thứ tự trong trận |
| `points` | `PositiveIntegerField` | Có | Snapshot điểm |
| `title_snapshot` | `CharField(max_length=200)` | Có | Snapshot title |
| `statement_snapshot` | `TextField` | Có | Snapshot nội dung đề |
| `starter_code_snapshot` | `TextField(blank=True)` | Không | Snapshot starter code |
| `difficulty_snapshot` | `CharField(max_length=20)` | Có | Snapshot difficulty |
| `first_solver` | `ForeignKey(MatchPlayer, null=True, blank=True, related_name="first_solved_problems")` | Không | Người nhận bonus |
| `first_solved_at` | `DateTimeField(null=True, blank=True)` | Không | Theo `Submission.received_at` |
| `created_at` | `DateTimeField(auto_now_add=True)` | Có | Audit |

### Constraints và indexes

* Unique: `(match, problem)`.
* Unique: `(match, order)`.
* Index: `match`, `problem`, `first_solver`.
* `points >= 1`.

### Ghi chú V1

* Battle page phải đọc `title_snapshot`, `statement_snapshot`, `starter_code_snapshot`, `difficulty_snapshot` và `points` từ `MatchProblem`.
* Battle page không đọc trực tiếp `Problem.statement` để tránh đổi đề giữa trận nếu admin sửa Problem.
* V1 không snapshot sample/hidden tests để tránh thêm bảng snapshot phức tạp trong demo.
* Hidden tests vẫn đọc từ `TestCase` tại thời điểm chấm, với quy tắc vận hành: admin không sửa TestCase của Problem đang dùng trong Match `PLAYING`.
* First-solve được lưu ở đây để mỗi bài chỉ có một first-solver.
* Khi xử lý first-solve phải dùng transaction.
* Nếu có accepted submission đến sau nhưng submission đến trước còn pending, chưa finalize first-solve vội.

---

## 10. Model: Submission

### App đề xuất

`submissions`

### Mục đích

Lưu mỗi lần Player submit code.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `match` | `ForeignKey(Match, related_name="submissions")` | Có | Trận |
| `player` | `ForeignKey(MatchPlayer, related_name="submissions")` | Có | Người submit |
| `match_problem` | `ForeignKey(MatchProblem, related_name="submissions")` | Có | Bài trong trận |
| `source_code` | `TextField` | Có | Code Python |
| `language` | `CharField(default="PYTHON")` | Có | V1 chỉ Python |
| `verdict` | `CharField(choices, default="PENDING")` | Có | Verdict chuẩn hóa |
| `received_at` | `DateTimeField(auto_now_add=True)` | Có | Thời điểm server nhận |
| `completed_at` | `DateTimeField(null=True, blank=True)` | Không | Thời điểm chấm xong |
| `judge_token` | `CharField(max_length=100, blank=True)` | Không | Token từ Judge0 nếu có |
| `runtime_ms` | `PositiveIntegerField(null=True, blank=True)` | Không | Runtime |
| `memory_kb` | `PositiveIntegerField(null=True, blank=True)` | Không | Memory |
| `judge_message` | `TextField(blank=True)` | Không | Lỗi/ghi chú kiểm soát được |
| `is_score_processed` | `BooleanField(default=False)` | Có | Đã chạy scoring chưa |

### Choices

```text
PENDING
ACCEPTED
WRONG_ANSWER
COMPILATION_ERROR
RUNTIME_ERROR
TIME_LIMIT_EXCEEDED
INTERNAL_ERROR
```

### Constraints và indexes

* Index: `match`, `player`, `match_problem`.
* Index: `verdict`, `received_at`.
* Index: `is_score_processed`.

### Ghi chú V1

* Submission sau deadline bị từ chối ở service, không tạo record và không gọi Judge0.
* Submission nhận trước hoặc đúng deadline vẫn được chấm dù Judge0 hoàn thành sau deadline.
* Source code không trả trong state endpoint.
* Hidden tests không lưu trong Submission.

---

## 11. Model: PlayerProblemProgress

### App đề xuất

`gameplay`

### Mục đích

Lưu trạng thái từng Player đối với từng MatchProblem. Đây là nguồn truth cho bài đã solved và điểm đã awarded.

### Fields

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `match` | `ForeignKey(Match, related_name="problem_progress")` | Có | Trận |
| `player` | `ForeignKey(MatchPlayer, related_name="problem_progress")` | Có | Người chơi |
| `match_problem` | `ForeignKey(MatchProblem, related_name="player_progress")` | Có | Bài |
| `is_solved` | `BooleanField(default=False)` | Có | Đã accepted lần đầu |
| `solved_at` | `DateTimeField(null=True, blank=True)` | Không | Theo `Submission.received_at` |
| `base_points_awarded` | `PositiveIntegerField(default=0)` | Có | Điểm base đã cộng |
| `first_solve_bonus_awarded` | `PositiveIntegerField(default=0)` | Có | 0 hoặc 1 |
| `accepted_submission` | `ForeignKey(Submission, null=True, blank=True, related_name="accepted_progress")` | Không | Submission đầu tiên được tính |
| `updated_at` | `DateTimeField(auto_now=True)` | Có | Audit |

### Constraints và indexes

* Unique: `(player, match_problem)`.
* Index: `match`, `player`, `match_problem`, `is_solved`.
* `base_points_awarded >= 0`.
* `first_solve_bonus_awarded` chỉ nên là `0` hoặc `1`. Có thể enforce bằng service hoặc DB check.

### Ghi chú V1

* Accepted lại bài đã solved không cộng điểm thêm.
* `MatchPlayer.score` phải bằng tổng:

```text
sum(base_points_awarded + first_solve_bonus_awarded)
```

* Progress giúp state endpoint đọc nhanh solved problem IDs mà không cần scan toàn bộ Submission.

---

## 12. Luồng ghi dữ liệu chính

### 12.1. Create room

```text
Create Match(status=WAITING, host=user, room_code=XXXXXX)
Create MatchPlayer(match, user, is_host=True)
```

### 12.2. Join room

```text
Validate Match.status = WAITING
Validate players.count < 2
Validate user chưa ở trong match
Create MatchPlayer(match, user, is_host=False)
```

### 12.3. Start match

```text
Validate requester là host
Validate Match.status = WAITING
Validate đúng 2 MatchPlayer
Select 2 Easy + 2 Medium active Problems
Create 4 MatchProblem với points/title/statement/starter_code/difficulty snapshot
Create PlayerProblemProgress cho 2 player x 4 problem
Update Match.status = PLAYING
Set Match.started_at
```

### 12.4. Submit

```text
Validate player thuộc match
Validate match đang PLAYING
Validate match_problem thuộc match
Validate received_at <= ends_at
Create Submission(verdict=PENDING)
Call JudgeService
Update Submission verdict/completed_at/judge fields
If ACCEPTED: call ScoringService
```

### 12.5. Scoring accepted submission

```text
Open transaction
Lock/read PlayerProblemProgress(player, match_problem)
If already solved: do not add score
Set solved, solved_at, base_points_awarded
Add base score to MatchPlayer.score immediately
If no earlier pending submission: finalize first-solve by received_at
If current player wins first-solve: set MatchProblem.first_solver, bonus=1, add bonus to score
Mark Submission.is_score_processed = True
Commit
```

---

## 13. First-solve rule chi tiết

First-solve dựa trên `Submission.received_at`, không dựa trên Judge0 completion time.

Rule an toàn:

* Chỉ accepted submission mới có khả năng nhận first-solve.
* Nếu có submission cùng `match_problem` đến sớm hơn, chưa completed, và thuộc đối thủ, chưa finalize bonus cho submission đến sau.
* Khi các submission đến sớm hơn đã có verdict không Accepted, submission accepted đến sau có thể nhận first-solve.
* `MatchProblem.first_solver` chỉ được set một lần.

Implementation V1 chốt theo hướng:

* Base score được cộng ngay khi submission Accepted đầu tiên của Player cho bài đó được xử lý.
* First-solve bonus chỉ finalize khi không còn earlier pending submission cho cùng `match_problem`.
* Nếu còn earlier pending submission, `first_solve_bonus_awarded = 0` tạm thời và `MatchProblem.first_solver = null`.
* Khi earlier pending submission hoàn tất, `ScoringService` phải chạy lại bước finalize first-solve cho `match_problem`.
* Bonus `+1` được cộng đúng một lần cho Player thắng first-solve.
* Cần test case Judge completion out-of-order.

---

## 14. State endpoint đọc gì

`GET /matches/<id>/state/` nên đọc:

* `Match.status`, `started_at`, `duration_seconds`, `winner`, `is_draw`.
* `MatchPlayer.score`.
* `PlayerProblemProgress.is_solved`.
* `MatchProblem.first_solver`.

Endpoint này không được:

* Gọi Judge0.
* Write database.
* Trả source code.
* Trả hidden tests.
* Scan toàn bộ Submission nếu không cần.

---

## 15. Admin behavior

Django Admin quản lý:

* Problem.
* TestCase inline theo Problem.
* Submission read-only hoặc inspection cơ bản.
* Match read-only hoặc inspection cơ bản.

V1 không xây custom admin UI.

---

## 16. Test cases bắt buộc cho database

### Problem và TestCase

* Player chỉ thấy sample tests.
* Hidden tests không xuất hiện trong response.
* Inactive Problem không được chọn cho match mới.

### Room và Match

* Room code unique.
* Một Match không quá 2 Player.
* Một User không join cùng Match hai lần.
* Match không thể đồng thời có `winner` và `is_draw = true`.
* Chỉ host start được.
* Start tạo đúng 4 MatchProblem.
* MatchProblem snapshot points/title/statement/starter_code/difficulty.

### Submission và scoring

* Accepted lần đầu cộng base score.
* Accepted lại không cộng điểm lần hai.
* Wrong Answer không cộng điểm.
* Submission sau deadline bị từ chối.
* Submission trước deadline nhưng Judge hoàn thành sau deadline vẫn được tính.
* First-solve chỉ cộng cho một Player.
* First-solve dựa trên `received_at`.
* Base score được cộng trước, first-solve bonus có thể finalize sau nếu còn earlier pending submission.
* Judge completion out-of-order vẫn chọn đúng first-solver.
* `MatchPlayer.score` khớp tổng progress.

### State endpoint

* Không write database.
* Không trả hidden tests.
* Không trả source code.
* Không tạo N+1 query.

---

## 17. Việc chưa làm trong tài liệu này

Tài liệu này chưa viết code Django models. Sau khi được nhóm duyệt, bước tiếp theo là:

```text
django-admin startproject config .
python manage.py startapp accounts
python manage.py startapp problems
python manage.py startapp matches
python manage.py startapp submissions
python manage.py startapp gameplay
```

Sau đó hiện thực models theo tài liệu này và tạo migrations.
