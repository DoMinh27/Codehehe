
# TÀI LIỆU 5 — DECISION LOG

**Tên file:** `15-decision-log.md`

## Cách sử dụng

Mỗi quyết định mới phải ghi:

* ID.
* Ngày.
* Trạng thái.
* Bối cảnh.
* Quyết định.
* Lý do.
* Hệ quả.
* Điều kiện xem xét lại.

---

## DEC-001 — Tên sản phẩm

**Trạng thái:** Approved

**Quyết định:** Tên chính thức là CodeHehe.

**Lý do:** Đây là tên dự án được nhóm sử dụng trong kế hoạch hiện tại.

**Hệ quả:** Tất cả tài liệu nhắc “Code Arena” phải đổi thành CodeHehe.

---

## DEC-002 — Mục tiêu sản phẩm

**Trạng thái:** Approved

**Quyết định:** CodeHehe là coding battle 1v1 có định hướng Energy, Skills, Defense, Minigames và Elo.

**Lý do:** Sự khác biệt dài hạn không nằm ở online judge đơn thuần mà ở gameplay cạnh tranh và game hóa.

**Hệ quả:** Energy và Skills phải xuất hiện trong Product Vision và Roadmap dù chưa triển khai V1.

---

## DEC-003 — Phạm vi V1

**Trạng thái:** Approved

**Quyết định:** V1 chỉ xây Coding Battle Core.

**Bao gồm:**

* Auth.
* Problem Bank.
* Room.
* Match.
* Judge.
* Score.
* First-solve.
* Timer.
* Polling.
* Result.

**Không bao gồm:**

* Energy.
* Skills.
* Minigames.
* Elo.
* Matchmaking tự động.

**Lý do:** Đội ngũ có bốn tuần và chưa có kinh nghiệm full-stack.

---

## DEC-004 — Chuyển từ FastAPI sang Django

**Trạng thái:** Approved; thay thế kiến trúc cũ

**Bối cảnh:** Kiến trúc cũ sử dụng FastAPI, React, PostgreSQL, Redis và Socket.IO.

**Quyết định:** V1 sử dụng Django monolith.

**Lý do:**

* Giảm số công nghệ.
* Django có sẵn Auth, ORM, Migration, Templates và Admin.
* Dễ học và giải thích.
* Giảm rủi ro tích hợp frontend/backend.
* Phù hợp năng lực nhóm.

**Hệ quả:** FastAPI không được dùng trong V1.

**Xem xét lại khi:** Cần tách một service độc lập có lý do rõ ràng sau V1.

---

## DEC-005 — Frontend V1

**Trạng thái:** Approved

**Quyết định:** Dùng Django Templates, HTML, CSS và Vanilla JavaScript.

**Lý do:** React làm tăng độ phức tạp state, API và build pipeline.

**Hệ quả:** Không dùng React, Vite, TypeScript hoặc Zustand trong V1.

---

## DEC-006 — Database V1

**Trạng thái:** Approved

**Quyết định:** Dùng SQLite.

**Lý do:**

* Không cần cài database server.
* Dễ chạy trên ba máy.
* Đủ cho quy mô demo nhỏ.

**Rủi ro:** Concurrent write và `database is locked`.

**Biện pháp:**

* Không write trong polling.
* Transaction ngắn.
* Theo dõi khi load test.

**Xem xét lại khi:** SQLite lock xuất hiện thường xuyên hoặc cần nhiều trận đồng thời.

---

## DEC-007 — Authentication

**Trạng thái:** Approved

**Quyết định:** Dùng Django Auth và Session.

**Lý do:** Không cần tự xây JWT flow.

**Hệ quả:** Không dùng JWT trong V1.

---

## DEC-008 — Admin

**Trạng thái:** Approved

**Quyết định:** Dùng Django Admin quản lý Problem và TestCase.

**Lý do:** Không dành thời gian xây custom CRUD admin.

---

## DEC-009 — Room code thay Matchmaking

**Trạng thái:** Approved

**Quyết định:** Player tạo phòng và mời đối thủ bằng mã 6 ký tự.

**Lý do:** Automatic matchmaking yêu cầu queue, Redis, lock và presence.

**Hệ quả:** Không có matchmaking tự động trong V1.

---

## DEC-010 — Polling thay WebSocket

**Trạng thái:** Approved

**Quyết định:**

* Battle polling khoảng một giây.
* Waiting Room polling khoảng hai giây.

**Lý do:** Polling dễ hiểu, dễ debug và đủ cho demo.

**Hệ quả:** Không dùng Socket.IO, Channels hoặc Redis trong V1.

**Điều kiện:** State endpoint phải nhẹ và không N+1.

---

## DEC-011 — Judge0

**Trạng thái:** Approved

**Quyết định:** Judge0 chịu trách nhiệm chạy code Python.

**Lý do:** Không tự xây sandbox.

**Hệ quả:**

* Không dùng `exec()`.
* Không dùng `eval()`.
* Judge0 phải nằm sau JudgeService.

---

## DEC-012 — FakeJudgeService

**Trạng thái:** Approved

**Quyết định:** Xây FakeJudgeService cùng interface với Judge0Service.

**Lý do:** Cho phép các thành viên phát triển Submission và Battle mà không bị Judge0 block.

---

## DEC-013 — Judge0 là Gate quan trọng nhất

**Trạng thái:** Approved

**Quyết định:**

* Judge Spike bắt đầu cuối Tuần 1.
* Judge thật phải chạy trong Tuần 2.
* Không được trượt sang Tuần 3.

**Hệ quả:** Nếu Gate 1 không đạt, dừng feature phụ.

---

## DEC-014 — Submission language

**Trạng thái:** Approved

**Quyết định:** V1 chỉ hỗ trợ Python.

**Lý do:** Giảm complexity Judge0 và phù hợp người dùng mục tiêu.

---

## DEC-015 — Số bài và thời lượng

**Trạng thái:** Approved

**Quyết định:**

* 4 bài mỗi trận.
* 2 Easy.
* 2 Medium.
* 15 phút.

**Lý do:** Đủ tạo nhiều lần cạnh tranh First-solve nhưng vẫn phù hợp demo và người mới.

---

## DEC-016 — Frozen problem list

**Trạng thái:** Approved

**Quyết định:** Khi Start Match, server tạo MatchProblem cố định.

**Lý do:** Đảm bảo hai người nhận cùng bài và việc sửa Problem không làm thay đổi trận.

**Hệ quả:** Không random lại trong trận.

---

## DEC-017 — Independent progression

**Trạng thái:** Approved

**Quyết định:** Hai Player giải bài độc lập, không bắt buộc theo thứ tự.

**Lý do:** Tránh dependency giữa bài và giữ công bằng.

---

## DEC-018 — Base score

**Trạng thái:** Approved

**Quyết định mặc định:**

* Easy: 1.
* Medium: 2.
* Hard: 3.

**Hệ quả:** MatchProblem snapshot points khi bắt đầu.

---

## DEC-019 — First-solve bonus

**Trạng thái:** Approved

**Quyết định:** Người Accepted bài trước nhận `+1`.

**Lý do:** Tạo cạnh tranh trực tiếp về tốc độ.

**Hệ quả:** Scoring phức tạp hơn và cần transaction, idempotency, concurrency tests.

---

## DEC-020 — First-solve ordering

**Trạng thái:** Approved

**Quyết định:** First-solve dựa trên `received_at`, không dựa trên Judge completion time.

**Lý do:** Judge0 có thể xử lý submission sai thứ tự.

**Hệ quả:** Phải xử lý earlier pending submission trước khi finalize bonus.

---

## DEC-021 — Submit trước deadline

**Trạng thái:** Approved

**Quyết định:** Submission được nhận trước hoặc đúng deadline vẫn được tính dù Judge hoàn thành sau deadline.

**Lý do:** Player không nên bị thiệt do tốc độ Judge0.

---

## DEC-022 — Submit sai

**Trạng thái:** Approved

**Quyết định:** Không trừ điểm khi submit sai trong V1.

**Lý do:** Đơn giản hóa gameplay và phù hợp người mới.

---

## DEC-023 — Match ending

**Trạng thái:** Approved

**Quyết định:** Match kết thúc khi:

* Hết 15 phút; hoặc
* Cả hai Player giải toàn bộ bài.

Nếu chỉ một Player giải hết, Match tiếp tục.

---

## DEC-024 — Match result khi bằng điểm

**Trạng thái:** Approved

**Quyết định:** Người có tổng điểm cao hơn thắng. Nếu hai Player bằng điểm, Match có kết quả Draw.

**Lý do:** Luật hòa dễ hiểu, dễ demo, tránh làm V1 phức tạp vì phải giải thích thêm tie-break phụ.

**Hệ quả:** V1 không dùng số bài đã giải hoặc thời điểm đạt final score để phân thắng thua khi tổng điểm bằng nhau.

---

## DEC-025 — Server authoritative state

**Trạng thái:** Approved

**Quyết định:** Backend quyết định:

* Verdict.
* Score.
* First-solve.
* Timer.
* Winner.
* Match status.

**Hệ quả:** Frontend chỉ gửi source code và action.

---

## DEC-026 — Hidden tests

**Trạng thái:** Approved

**Quyết định:** Hidden tests không bao giờ được gửi về browser.

**Hệ quả:** Phải có automated test kiểm tra response.

---

## DEC-027 — Refresh và disconnect

**Trạng thái:** Approved

**Quyết định:**

* Refresh được phép.
* Disconnect không pause.
* Không xử thua tự động.
* Player có thể quay lại Match.

---

## DEC-028 — Service layer

**Trạng thái:** Approved

**Quyết định:** Business logic quan trọng phải nằm trong service.

**Service V1:**

* JudgeService.
* SubmissionService.
* ScoringService.
* MatchService.

**Lý do:** Chuẩn bị đường nâng cấp Energy và Skills.

---

## DEC-029 — MatchPlayer từ V1

**Trạng thái:** Approved

**Quyết định:** V1 phải có MatchPlayer.

**Lý do:** Đây là nơi lưu score và sau này mở rộng:

* Energy.
* Shield.
* Elo.
* Effects.

---

## DEC-030 — Energy roadmap

**Trạng thái:** Approved for future version

**Quyết định:**

* Solve mới: +1 Energy.
* Max Energy: 3.
* Hint: -1 Energy.

**Phiên bản:** V1.5.

---

## DEC-031 — Defense roadmap

**Trạng thái:** Approved for future version

**Quyết định:** Chỉ giữ:

* Cleanse.
* Reflect.
* Shield.

---

## DEC-032 — Minigames roadmap

**Trạng thái:** Approved for future version

**Quyết định:** Các minigame định hướng:

* Flappy Bird.
* Dinosaur.
* Math.
* Typing.

---

## DEC-033 — Skip

**Trạng thái:** Deferred

**Quyết định:** Không triển khai V1.

**Lý do:** Chưa có rule đảm bảo không phá frozen list và fairness.

---

## DEC-034 — Elo

**Trạng thái:** Deferred to V4

**Quyết định:** Elo không nằm trong V1.

---

## DEC-035 — Azure timing

**Trạng thái:** Approved

**Quyết định:**

* Không deploy Azure trong những ngày đầu.
* Deploy skeleton cuối Tuần 2 hoặc đầu Tuần 3.
* Deploy MVP đầu Tuần 4.

**Lý do:** Không học cloud đồng thời với toàn bộ core.

---

## DEC-036 — Azure complexity

**Trạng thái:** Approved

**Quyết định:** Không sử dụng:

* Kubernetes.
* Service Bus.
* Azure Redis.
* Microservices.
* Autoscaling phức tạp.

trong V1.

---

## DEC-037 — Documentation time-box

**Trạng thái:** Approved

**Quyết định:** System Design và Database Design phải chốt trong hai ngày đầu.

**Lý do:** Tài liệu phải hướng dẫn development nhưng không trở thành blocker hành chính.

---

## DEC-038 — Git workflow

**Trạng thái:** Approved

**Quyết định:**

* Không push trực tiếp `main`.
* Mỗi task có branch.
* Mỗi PR có reviewer.
* `main` phải luôn chạy được.

---

## DEC-039 — Task ownership

**Trạng thái:** Approved

**Quyết định:** Mỗi task có đúng một owner chính.

**Lý do:** Tránh hai người sửa cùng logic và giẫm chân nhau.

---

## DEC-040 — Codex governance

**Trạng thái:** Approved

**Quyết định:** Codex chỉ làm task có:

* Goal.
* Scope.
* Allowed files.
* Acceptance criteria.
* Constraints.
* Out of scope.
* Manual test.

**Hệ quả:** Không dùng prompt “xây toàn bộ hệ thống”.

---

## DEC-041 — Feature freeze

**Trạng thái:** Approved

**Quyết định:** Feature freeze bắt đầu giữa Tuần 4.

**Sau feature freeze chỉ được:**

* Fix bug.
* Test.
* Deploy.
* Cập nhật tài liệu.
* Polish nhỏ không rủi ro.

---

## DEC-042 — Definition of success

**Trạng thái:** Approved

**Quyết định:** Thành công không được đo bằng số công nghệ hoặc số lượng feature.

Thành công được đo bằng:

* Chạy được.
* Hiểu được.
* Sửa được.
* Test được.
* Deploy được.
* Demo được.
* Bảo vệ được.
* Có đường nâng cấp Energy và Skills.

---

## DEC-043 — Runtime chính thức

**Trạng thái:** Approved

**Quyết định:**

* Python 3.12.
* Django 5.2 LTS.

**Lý do:** Chốt version giúp cả ba máy phát triển, môi trường demo và tài liệu setup thống nhất.

**Hệ quả:** `requirements.txt`, `.venv`, tài liệu setup và deployment phải bám theo version này.

---

## DEC-044 — Judge0 hosting V1

**Trạng thái:** Approved

**Quyết định:** V1 dùng Judge0 external endpoint trước, cấu hình URL/key qua `.env`.

**Lý do:** Giảm rủi ro hạ tầng trong bốn tuần, không phải tự vận hành sandbox ngay từ đầu.

**Hệ quả:**

* Không self-host Judge0 trong những ngày đầu.
* Không commit endpoint secret hoặc API key.
* FakeJudgeService vẫn được dùng trong phát triển nội bộ khi external endpoint lỗi hoặc chưa sẵn sàng.

---

## DEC-045 — Problem content snapshot V1

**Trạng thái:** Approved

**Bối cảnh:** Nếu Battle page đọc trực tiếp `Problem.statement`, admin sửa Problem giữa Match `PLAYING` có thể làm nội dung đề đổi ngay trong trận.

**Quyết định:** Khi Start Match, `MatchProblem` snapshot:

* `points`.
* `title`.
* `statement`.
* `starter_code`.
* `difficulty`.

V1 không snapshot `TestCase`.

**Lý do:** Snapshot nội dung hiển thị giúp Player không bị đổi đề giữa trận, nhưng không cần thêm bảng TestCase snapshot để giữ V1 đơn giản.

**Hệ quả:**

* Battle page đọc nội dung từ `MatchProblem`, không đọc trực tiếp từ `Problem`.
* Judge vẫn đọc TestCase hiện tại từ `Problem`.
* Admin không được sửa TestCase của Problem đang dùng trong Match `PLAYING`.

**Xem xét lại khi:** Cần bảo vệ tuyệt đối lịch sử chấm hoặc cho phép admin sửa TestCase trong lúc nhiều trận đang chạy.

---

## DEC-046 — Match winner/draw invariant

**Trạng thái:** Approved

**Quyết định:** Match không được đồng thời có `winner != null` và `is_draw = true`.

**Lý do:** Hai field này biểu diễn hai kết quả loại trừ nhau. Nếu không khóa, bug trong code có thể tạo trạng thái mâu thuẫn.

**Hệ quả:**

* Model `Match` cần `CheckConstraint`.
* Test phải kiểm tra không tạo được Match vừa có winner vừa là draw.

---

## DEC-047 — First-solve finalize strategy

**Trạng thái:** Approved

**Bối cảnh:** First-solve dựa trên `received_at`, trong khi Judge0 có thể hoàn thành submission sai thứ tự.

**Quyết định:** V1 dùng chiến lược:

* Base score được cộng ngay khi một Player có Accepted đầu tiên cho bài đó.
* First-solve bonus chỉ finalize khi không còn earlier pending submission cho cùng `MatchProblem`.
* Nếu còn earlier pending submission, bonus tạm thời chưa cộng.
* Khi earlier pending submission hoàn tất, `ScoringService` chạy lại bước finalize first-solve cho bài đó.

**Lý do:** Player thấy base score nhanh, nhưng bonus vẫn đúng theo luật `received_at`.

**Hệ quả:**

* UI có thể có trạng thái score tăng base trước, bonus tăng sau.
* Cần test Judge completion out-of-order.
* `MatchProblem.first_solver` chỉ được set một lần.
* `first_solve_bonus_awarded` chỉ được cộng một lần.
