const BASE_URL = 'http://127.0.0.1:7860/api';

export const fetcher = (url: string) => fetch(`${BASE_URL}${url}`).then(res => res.json());
