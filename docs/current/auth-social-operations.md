# Auth, Social và Operations

## Tài khoản và email

- Đăng nhập tiếp tục dùng username
- Đăng ký hợp lệ tạo `PendingRegistration`, chưa tạo `User` hoặc `AccountEmail`
- Mật khẩu chỉ được lưu dưới dạng password hash
- Link xác minh có hiệu lực 5 phút; bản ghi có thể được giữ tối đa 2 giờ để gửi
  lại nếu username/email chưa bị đăng ký khác lấy
- GET link xác minh chỉ mở trang xác nhận; POST có CSRF mới tạo atomically một
  User active và AccountEmail đã xác minh
- Password reset chỉ áp dụng cho email đã xác minh của tài khoản active; link có
  hiệu lực mặc định 1 giờ
- Response resend/reset trung tính để hạn chế dò tài khoản; rate limit mặc định
  10 request/IP/giờ và 3 request/email/giờ cho từng luồng
- Local dùng console email backend; production dùng SMTP qua biến môi trường

## Bạn bè, presence và lời mời

- Friendship và FriendRequest dùng cặp user canonical để ngăn lời mời trùng hai
  chiều
- Lời mời kết bạn có hiệu lực 30 ngày; sau khi từ chối, cùng người gửi phải chờ
  24 giờ
- Mỗi tài khoản có tối đa 100 bạn, 20 lời mời đã gửi đang chờ và 10 lần gửi mỗi
  giờ
- Người dùng có thể hủy kết bạn, chặn/bỏ chặn và chọn ẩn presence
- Presence heartbeat mặc định 30 giây; quá 90 giây được xem là Không hoạt động
- WAITING và PLAYING được ưu tiên thành trạng thái Trong phòng và Đang trong trận
- Chỉ bạn bè đã xác nhận nhìn thấy trạng thái; offline và ẩn được trình bày giống
  nhau với người khác

Direct Match Invitation chỉ gửi giữa hai người đang là bạn và cùng Sẵn sàng.
Lời mời tồn tại 120 giây, giới hạn ba incoming/outgoing đang chờ và năm lần gửi
trong 10 phút. Accept kiểm tra lại friendship, block và availability trong
transaction rồi tạo một phòng Classic mới.

## Notification Shell và Rematch

Chuông notification xuất hiện trên các trang authenticated trừ Battle. Badge chỉ
đếm item incoming cần xử lý; outgoing vẫn nằm trong nhóm chờ nhưng không tăng
badge. Server tạo projection tối đa 20 item từ:

- lời mời kết bạn;
- lời mời tái đấu;
- lời mời đấu trực tiếp.

Result chỉ có nút gửi lời mời tái đấu gọn. Người nhận đồng ý/từ chối trong
Notification Shell; người gửi được active-match polling chuyển tới phòng mới.
Notification không lưu read/unread hoặc lịch sử và không dùng GenericForeignKey.

## Fair Play

Battle ghi heartbeat, khoảng tab/page bị ẩn và số ký tự paste. Dưới 1 giây bị bỏ
qua; từ 1 đến dưới 3 giây chỉ audit; từ 3 giây cộng strike. Hai strike hoặc tổng
10 giây vắng sẽ gắn cờ, còn connection gap 30 giây tạo cờ riêng mà không cộng
strike. Tín hiệu chỉ phục vụ admin xem xét, không tự xử thua.

## Operations Dashboard V2

Dashboard tại `/admin/dashboard/` dành cho superuser hoặc staff có permission
`operations.view_operations_dashboard`. Năm tab gồm Tổng quan, Trận đấu, Hàng
đợi, Fair Play và Hệ thống.

Dashboard là read-only và dẫn tới Django Admin để xử lý chi tiết. Nó tổng hợp:

- Database, Judge0, AI Worker và Match Sweeper health
- Trận đang chạy, submission pending/stale và AI Review queue
- Cảnh báo phòng chờ lâu, trận quá giờ, worker stale/failure và Fair Play
- KPI 24 giờ và người chơi cần xem xét

Django Admin vẫn là nơi chỉnh Problem/TestCase, Match, Energy, inventory Kỹ năng
và các model vận hành. Dashboard không retry job, finalize trận hoặc sửa dữ liệu
trực tiếp.
