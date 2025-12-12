export async function apiFetch(url: string, options: RequestInit = {}) {
    const token = localStorage.getItem("token");

    const headers = {
        ...options.headers,
        'Authorization': token ? `Bearer ${token}` : '',
    };

    const response = await fetch(url, {
        ...options,
        headers: headers as HeadersInit,
    });

    if (response.status === 401) {
        // Token expired or invalid
        localStorage.removeItem("token");
        window.location.href = "/login";
        throw new Error("Unauthorized");
    }

    return response;
}
