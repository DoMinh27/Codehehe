# Tài liệu CodeHehe

Thư mục này phân biệt tài liệu hiện hành với các bản thiết kế lịch sử. Khi tài
liệu mâu thuẫn với mã nguồn, model, migration hoặc test trên nhánh đang chạy,
mã nguồn và migration là nguồn sự thật kỹ thuật cuối cùng.

## Bắt đầu từ đây

Đọc theo thứ tự sau nếu mới tham gia dự án:

1. [Sản phẩm hiện tại](current/product.md)
2. [Kiến trúc hiện tại](current/architecture.md)
3. [Gameplay v3.2](current/gameplay-v3.2.md)
4. [Auth, Social và Operations](current/auth-social-operations.md)
5. [Roadmap hiện hành](current/roadmap.md)

## Tài liệu đang có hiệu lực

| Tài liệu | Vai trò |
|---|---|
| [Judge0 setup](07-judge0-setup.md) | Cấu hình và kiểm tra Judge0 |
| [Deployment](08-deployment.md) | Runbook triển khai Azure VM |
| [Decision log](15-decision-log.md) | Lịch sử quyết định kỹ thuật và sản phẩm |
| [Problem attribution](18-problem-attribution.md) | Nguồn và giấy phép ngân hàng đề |
| [MatchEvent và Rematch](19-match-events-rematch.md) | Timeline sau trận và tái đấu |
| [Fair Play Monitor](21-fair-play-monitor.md) | Tín hiệu rời trận và giới hạn sử dụng |

## Tài liệu lịch sử

Các baseline V1–V3 cũ được giữ tại [`archive/v1-v3/`](archive/v1-v3/) để tra cứu
quá trình phát triển. Chúng không còn mô tả đầy đủ hệ thống hiện tại và không
được dùng làm hướng dẫn deploy hoặc tiêu chí nghiệm thu mới.

## Tài liệu riêng tư

Tài liệu phục vụ vấn đáp, ảnh render và ghi chú cá nhân nằm trong
`docs/defense/`. Khu vực này không thuộc tài liệu public của repository và
không được stage hoặc commit.
