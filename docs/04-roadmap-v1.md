# TÀI LIỆU 4 — ROADMAP 4 TUẦN

**Tên file đề xuất:** `04-roadmap-v1.md`

## 1. Nguyên tắc roadmap

Roadmap được tổ chức theo vertical slice và delivery gate.

Không phát triển theo cách:

```text
A làm toàn bộ backend
B làm toàn bộ frontend
C làm toàn bộ Judge
→ cuối tháng mới ghép
```

Mỗi tuần phải có một flow tích hợp có thể demo.

---

## 2. Delivery Gates

### Gate 0 — Foundation Ready

Deadline: Cuối Ngày 3, Tuần 1.

Điều kiện:

* Repository hoạt động.
* Ba máy chạy Django.
* `/health/` hoạt động.
* Base template hoạt động.
* FakeJudgeService tồn tại.

### Gate 1 — Submission hoạt động

Deadline: Giữa hoặc cuối Tuần 2.

Điều kiện:

```text
Problem
→ nhập Python
→ Submit
→ hidden tests
→ Judge0
→ verdict
→ lưu Submission
```

### Gate 2 — Room hoạt động

Deadline: Cuối Tuần 2.

Điều kiện:

```text
A tạo phòng
→ B join
→ hai người cùng Match
→ người thứ ba bị từ chối
```

### Gate 3 — Playable MVP

Deadline: Cuối Tuần 3.

Điều kiện:

```text
Create Room
→ Join
→ Start
→ Submit
→ Score
→ First-solve
→ Timer
→ Result
```

### Gate 4 — Release Candidate

Deadline: Giữa Tuần 4.

Điều kiện:

* Core ổn định.
* Không còn blocker.
* Deployment hoạt động.
* Feature freeze bắt đầu.

### Gate 5 — Final Release

Deadline: Cuối Tuần 4.

Điều kiện:

* Demo ổn định.
* Slide hoàn thành.
* Video backup.
* Question Bank.
* Source code sạch.
* Tài liệu cập nhật.

---

## 3. Tuần 1 — Foundation và Judge Spike

## Mục tiêu tuần

```text
Admin tạo đề
→ Player đăng nhập
→ Player xem được đề
```

Đồng thời bắt đầu kiểm chứng Judge0.

### Ngày 1 — Baseline và repository

#### Cả nhóm

* Đọc và phê duyệt:

  * Project Charter.
  * PRD.
  * Gameplay Rules.
  * Roadmap.
  * Decision Log.
* Tạo GitHub repository.
* Tạo GitHub Project.
* Mời ba thành viên.
* Tạo branch protection cho `main`.
* Tạo các cột:

  * Backlog.
  * Ready.
  * In Progress.
  * Review.
  * Testing.
  * Done.
  * Blocked.

#### Thành viên A

* Bắt đầu Database Design.
* Liệt kê model và relation.
* Chốt MatchPlayer, MatchProblem, Submission và PlayerProblemProgress.

#### Thành viên B

* Vẽ User Flow.
* Vẽ wireframe:

  * Login.
  * Register.
  * Lobby.
  * Waiting Room.
  * Battle.
  * Result.

#### Thành viên C

* Viết Submit Flow.
* Định nghĩa JudgeService interface.
* Chuẩn bị test cases cho Judge Spike.

### Ngày 2 — Environment và technical baseline

#### Cả nhóm

Cài:

* Git.
* Python 3.12.
* VS Code.
* Python extension.
* Ruff extension.
* GitLens.
* SQLite Viewer.

Thực hiện:

* Clone repository.
* Tạo `.venv`.
* Cài dependency.
* Chạy cùng Python 3.12.
* Chốt `requirements.txt`.
* Tạo `.env.example`.
* Tạo `.gitignore`.

#### Thành viên A

* Hoàn tất Database Design bản đầu.
* Vẽ ERD.
* Chốt unique constraints.

#### Thành viên B

* Hoàn tất UI Flow.
* Chốt Battle layout.

#### Thành viên C

* Viết FakeJudgeService contract.
* Tạo script Judge0 Spike độc lập.

### Ngày 3 — Django skeleton

#### Thành viên A

* `django-admin startproject`.
* Tạo apps:

  * accounts.
  * problems.
  * matches.
  * submissions.
  * gameplay.
* Tạo root URL.
* Tạo `/health/`.
* Chạy migration.

#### Thành viên B

* Tạo `base.html`.
* Tạo static CSS/JS structure.
* Tạo layout cơ bản.

#### Thành viên C

* Tạo FakeJudgeService.
* Viết unit test FakeJudge.

#### Milestone

Cả ba máy chạy được:

```text
/health/
/admin/
```

### Ngày 4 — Auth và Problem models

#### A

* Register/Login/Logout.
* Problem model.
* TestCase model.
* Migrations.
* Django Admin.

#### B

* Login page.
* Register page.
* Lobby.
* Problem list/detail.

#### C

* Auth tests.
* Hidden test visibility tests.
* Judge0 connectivity thử nghiệm đầu tiên.

### Ngày 5 — Problem vertical slice và Judge Spike

#### A

* Hoàn thiện Problem Bank.
* Admin inline hoặc form quản lý TestCase.
* Seed data cơ bản.

#### B

* Hiển thị sample tests.
* Starter code textarea.
* Error states cơ bản.

#### C

* Judge0 tests:

  * Accepted.
  * Wrong Answer.
  * Syntax Error.
  * Runtime Error.
  * Time Limit.
* Ghi kết quả Spike.

#### Milestone cuối Tuần 1

```text
Admin tạo Problem
→ thêm sample/hidden tests
→ Player đăng nhập
→ Player chỉ thấy sample tests
```

---

## 4. Tuần 2 — Submission và Match Foundation

## Mục tiêu tuần

```text
Submit chạy end-to-end
và
A/B vào cùng một phòng
```

### Ngày 1 — Judge0 integration

#### C

* Hoàn thiện Judge0Service.
* Chuẩn hóa verdict.
* Xử lý timeout/network error.

#### A

* Tạo Submission model.
* Migration.
* Admin inspection.

#### B

* Submission UI.
* Loading state.
* Verdict panel.

### Ngày 2 — SubmissionService

#### C

* SubmissionService.
* Hidden test execution.
* Verdict mapping.
* Judge error handling.

#### A

* Submit view/route.
* Authorization checks.
* Transaction boundary.

#### B

* Fetch submit.
* Error message.
* Disable button khi request đang chạy.

### Ngày 3 — Gate 1

Kiểm thử:

* Accepted.
* Wrong Answer.
* Compilation Error.
* Runtime Error.
* Time Limit.
* Judge offline.
* Submission lưu database.
* Hidden tests không lộ.

Nếu Gate 1 chưa đạt:

* Cả nhóm dừng feature phụ.
* Không polish UI.
* Không làm Energy.
* Tập trung Judge và Submission.

### Ngày 4 — Match models

#### A

* Match.
* MatchPlayer.
* MatchProblem.
* PlayerProblemProgress.
* Migration.
* Constraints.

#### B

* Lobby Create/Join form.
* Waiting Room skeleton.

#### C

* Match model tests.
* Room code tests.
* Third-player tests.

### Ngày 5 — Create và Join Room

#### A

* CreateRoomService.
* JoinRoomService.
* Host assignment.
* Room code 6 ký tự.

#### B

* Create Room UI.
* Join Room UI.
* Waiting Room polling.

#### C

* Integration tests.
* Invalid code.
* Full room.
* Duplicate join.

#### Milestone cuối Tuần 2 — Gate 2

```text
Player A tạo phòng
→ Player B join
→ cả hai xuất hiện
→ người thứ ba bị từ chối
```

---

## 5. Tuần 3 — Playable Battle

## Mục tiêu tuần

Hai Player chơi hoàn chỉnh một trận.

### Ngày 1 — Start Match

#### A

* StartMatchService.
* Validate host.
* Validate đủ hai Player.
* Chọn 4 Problem.
* Tạo MatchProblem.
* Snapshot points.
* Lưu `started_at`, `ends_at`.

#### B

* Start button.
* Redirect Battle.
* Waiting state.

#### C

* Start Match tests.
* Frozen problem tests.
* Insufficient problem tests.

### Ngày 2 — Battle UI và Match Submit

#### A

* Validate Player thuộc Match.
* Validate Problem thuộc MatchProblem.
* Match submission endpoint.

#### B

* Battle layout.
* Problem navigation.
* Code textarea/editor.
* Submit integration.

#### C

* Submission trong Match.
* PlayerProblemProgress.

### Ngày 3 — Score và First-solve

#### C

* ScoringService.
* Base score.
* Duplicate protection.
* First-solve.
* `received_at`.
* Idempotency.
* Pending earlier submission handling.

#### A

* Transaction và constraints.
* MatchPlayer score update.

#### B

* Score display.
* First-solve indicator nếu có.

#### Checkpoint giữa Tuần 3

```text
Hai Player Start
→ Submit
→ Score thay đổi
→ Timer chạy
```

### Ngày 4 — Match State và Polling

#### A

* `/matches/<id>/state/`.
* Query optimization.
* Server timer.
* Finish logic.

#### B

* Polling một giây.
* Waiting polling hai giây.
* Dừng polling khi Finished.
* Opponent progress.

#### C

* State endpoint tests.
* Query count test.
* Timeout submission test.

### Ngày 5 — Result và Gate 3

#### A

* Winner calculation.
* Draw khi bằng điểm.
* `FINISHED`.
* Result authorization.

#### B

* Result page.
* Winner/Draw UI.
* Final scores.

#### C

* End-to-end tests.
* Concurrent first-solve tests.
* Judge completion out-of-order test.

#### Milestone cuối Tuần 3

Một trận hoàn chỉnh hoạt động end-to-end.

---

## 6. Tuần 4 — Stabilization và Release

## Mục tiêu tuần

Ổn định, triển khai và bảo vệ được.

### Ngày 1 — Deployment MVP

* Triển khai Django.
* Cấu hình environment.
* Migration.
* Static files.
* Admin account.
* Seed data.
* Judge endpoint.
* Health smoke test.

### Ngày 2 — Integration hardening

* Refresh/re-entry.
* Judge offline.
* Invalid state.
* Room full.
* Submission after timeout.
* Duplicate request.
* SQLite lock observation.

### Ngày 3 — Release Candidate và feature freeze

* Không thêm feature mới.
* Chỉ fix bug.
* Chạy manual E2E.
* Load test nhỏ.
* Kiểm tra polling query.
* Backup database.
* Chuẩn bị rollback.

### Ngày 4 — Presentation

* Slide.
* Architecture diagram.
* Product flow.
* Gameplay roadmap.
* Question Bank.
* Phân công người trình bày.

### Ngày 5 — Final rehearsal

* Chạy demo nhiều lần.
* Kiểm tra hai tài khoản.
* Kiểm tra code đúng/sai.
* Kiểm tra video backup.
* Final tag/release.
* Public source code nếu đã sẵn sàng.

---

## 7. Cắt scope khi trễ

Cắt theo thứ tự:

1. Animation.
2. Waiting Room UI phức tạp.
3. Submission history trong Battle.
4. Run Custom Input.
5. Rematch.
6. Profile.
7. Leaderboard.
8. Autosave source code.
9. UI polish phụ.

Không cắt:

* Auth.
* Problem Bank.
* Hidden tests.
* Judge0.
* Room.
* Match.
* Submission.
* Score.
* First-solve.
* Timer.
* Polling.
* Result.

---
