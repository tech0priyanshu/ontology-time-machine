from abc import ABC, abstractmethod
from proxy.http.parser import HttpParser
from typing import Tuple, Dict, Any
import base64
from ontologytimemachine.utils.config import logger


class AbstractRequestWrapper(ABC):
    def __init__(self, request: Any) -> None:
        self.request = request

    @abstractmethod
    def is_get_request(self) -> bool:
        pass

    @abstractmethod
    def is_connect_request(self) -> bool:
        pass

    @abstractmethod
    def is_head_request(self) -> bool:
        pass

    @abstractmethod
    def is_https_request(self) -> bool:
        pass

    @abstractmethod
    def get_request_host(self) -> str:
        pass

    @abstractmethod
    def get_request_path(self) -> str:
        pass

    @abstractmethod
    def set_request_path(self, new_path) -> None:
        pass
    
    @abstractmethod
    def set_request_host(self, new_host) -> None:
        pass

    @abstractmethod
    def get_request_headers(self) -> Dict[str, str]:
        pass

    @abstractmethod
    def get_request_accept_header(self) -> str:
        pass

    @abstractmethod
    def set_request_accept_header(self, mime_type: str) -> None:
        pass

    @abstractmethod
    def get_request_url_host_path(self) -> Tuple[str, str, str]:
        pass

    @abstractmethod
    def get_authentication_from_request(self) -> str:
        pass


class HttpRequestWrapper(AbstractRequestWrapper):
    def __init__(self, request: HttpParser) -> None:
        super().__init__(request)

    def is_get_request(self) -> bool:
        return self.request.method == b"GET"

    def is_connect_request(self) -> bool:
        return self.request.method == b"CONNECT"

    def is_head_request(self) -> bool:
        return self.request.method == b"HEAD"

    def is_https_request(self) -> bool:
        return self.request.method == b"CONNECT" or self.request.headers.get(
            b"Host", b""
        ).startswith(b"https")

    def get_request_host(self) -> str:
        if self.request.host:
            return self.request.host.decode("utf-8")
        else:
            return ""

    def get_request_path(self) -> str:
        if self.request.path:
            return self.request.path.decode("utf-8")
        else:
            return ""

    def set_request_path(self, new_path: str) -> None:
        self.request.path = new_path.encode("utf-8")
        logger.info(f"Request path set to: {new_path}")
    
    def set_request_host(self, new_host: str) -> None:
        self.request.host = new_host.encode("utf-8")
        logger.info(f"Request path set to: {new_host}")

    def get_request_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for k, v in self.request.headers.items():
            headers[v[0].decode("utf-8")] = v[1].decode("utf-8")
        return headers

    def get_request_accept_header(self) -> str:
        logger.info("Wrapper - get_request_accept_header")
        return self.request.headers[b"accept"][1].decode("utf-8")

    def set_request_accept_header(self, mime_type: str) -> None:
        self.request.headers[b"accept"] = (b"Accept", mime_type.encode("utf-8"))
        logger.info(f'Accept header set to: {self.request.headers[b"accept"][1]}')

    def get_request_url_host_path(self) -> Tuple[str, str, str]:
        logger.info("Get ontology from request")
        if (self.is_get_request or self.is_head_request) and not self.request.host:
            for k, v in self.request.headers.items():
                if v[0].decode("utf-8") == "Host":
                    host = v[1].decode("utf-8")
                    path = self.get_request_path()
                    break
            url = f"https://{host}{path}"
        else:
            host = self.get_request_host()
            path = self.get_request_path()
            url = f"http://{host}{path}"

        logger.info(f"Ontology: {url}")
        return url, host, path

    def get_authentication_from_request(self) -> str:
        is_auth = False
        # if b"authorization" in self.request.headers.keys():
        #     auth_header = self.request.headers[b"authorization"]
        #     is_auth = True
        if b"proxy-authorization" in self.request.headers.keys():
            auth_header = self.request.headers[b"proxy-authorization"]
            is_auth = True
        if is_auth:
            auth_header = auth_header[1]
            auth_type, encoded_credentials = auth_header.split()
            auth_type = auth_type.decode("utf-8")
            if auth_type.lower() != "basic":
                return None
            decoded_credentials = base64.b64decode(encoded_credentials).decode()
            logger.info(f'Decoded credentials: {decoded_credentials}')
            return decoded_credentials
        return None
