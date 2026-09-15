# Sản phẩm CodeHehe hiện tại

CodeHehe là nền tảng thi đấu lập trình 1v1 theo thời gian thực ở mức MVP. Hai
người chơi vào một phòng Classic, giải cùng bộ đề đã được snapshot và có thể
dùng Kỹ năng để tạo áp lực trong trận. Trạng thái live dùng polling HTTP; hệ
thống chưa dùng WebSocket.

## Luồng người chơi

- Đăng ký bằng username, email và mật khẩu; tài khoản chỉ được tạo sau khi xác
  minh email trong thời hạn 5 phút
- Đăng nhập bằng username; hỗ trợ gửi lại email xác minh và đặt lại mật khẩu
- Tạo phòng bằng mã sáu ký tự, tham gia phòng, chờ host bắt đầu rồi vào Battle
- Run Code với input tùy chỉnh và Submit để chấm bằng Judge0
- Xem điểm, Energy, Kỹ năng, hiệu ứng đang chịu và phản hồi chiến đấu dành riêng
  cho chính người xem
- Xem Result, Timeline, phân tích bài làm bằng AI theo yêu cầu và mời tái đấu
- Xem hồ sơ riêng tư, thống kê thắng–thua–hòa, streak hoạt động, lịch sử trận và
  toàn bộ source của chính mình

## Nội dung và gameplay

- Ngân hàng có 30 bài: 10 Easy, 12 Medium và 8 Hard
- 16 bài do CodeHehe tự xây và 14 bài chuyển thể từ Exercism Problem
  Specifications theo giấy phép MIT
- Mỗi bài có một sample và tám hidden test; hidden test và reference solution
  không được trả cho người chơi
- Trận Classic hiện dùng ruleset `v3.2`, kéo dài mặc định 5 phút và chọn ngẫu
  nhiên 2 Easy, 1 Medium, 1 Hard
- Bảy Kỹ năng hiện có: Đảo chiều code, Che mờ đề, Trừ thời gian, Thử thách gõ
  chữ, Thanh tẩy, Tước đoạt và Khiên

## Social và vận hành

- Notification Shell tổng hợp lời mời kết bạn, tái đấu và mời đấu đang chờ
- Người chơi có danh sách bạn bè, chặn/bỏ chặn, ẩn presence và các trạng thái
  Sẵn sàng, Trong phòng, Đang trong trận hoặc Không hoạt động
- Bạn bè đang Sẵn sàng có thể mời nhau vào một phòng Classic mới
- Fair Play Monitor ghi nhận tín hiệu rời trang, mất heartbeat và số lượng ký tự
  paste để admin xem xét; không tự kết luận gian lận hoặc xử thua
- Operations Dashboard V2 theo dõi Database, Judge0, worker, sweeper, trận live,
  queue submission/AI và tín hiệu Fair Play

## Giới hạn MVP

- Chưa có xếp hạng/Elo, mùa giải, matchmaking tự động hoặc chế độ đội
- Chưa có chat, spectator hoặc replay thao tác code theo thời gian
- SQLite và polling phù hợp cho quy mô demo/nhỏ; cần PostgreSQL, Redis và mô
  hình realtime phù hợp trước khi tăng tải đáng kể
- AI Review phụ thuộc nhà cung cấp bên ngoài và chỉ là nhận xét sau trận, không
  ảnh hưởng điểm hoặc kết quả
