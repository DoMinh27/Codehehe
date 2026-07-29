export class ApiError extends Error {
    constructor({code, message, status = 0, cause = null}) {
        super(message);
        this.name = "ApiError";
        this.code = code;
        this.status = status;
        this.cause = cause;
    }
}


async function parseResponse(response) {
    try {
        return await response.json();
    } catch (cause) {
        throw new ApiError({
            code: "INVALID_RESPONSE",
            message: "Máy chủ trả về dữ liệu không hợp lệ.",
            status: response.status,
            cause,
        });
    }
}


export function createBattleApi({fetchImpl = window.fetch.bind(window)} = {}) {
    async function request(url, options = {}) {
        let response;
        try {
            response = await fetchImpl(url, options);
        } catch (cause) {
            throw new ApiError({
                code: "NETWORK_ERROR",
                message: "Không thể kết nối đến máy chủ.",
                cause,
            });
        }

        const payload = await parseResponse(response);
        if (!response.ok) {
            throw new ApiError({
                code: payload?.code || "REQUEST_FAILED",
                message: payload?.message || "Yêu cầu không thành công.",
                status: response.status,
            });
        }
        return payload;
    }

    return {
        getJson(url) {
            return request(url, {
                headers: {"Accept": "application/json"},
            });
        },
        post(url, csrfToken) {
            return request(url, {
                method: "POST",
                headers: {"X-CSRFToken": csrfToken},
            });
        },
        postJson(url, payload, csrfToken) {
            return request(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(payload),
            });
        },
    };
}
