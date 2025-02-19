import logging
from proxy.http.proxy import HttpProxyBasePlugin
from proxy.http import httpHeaders
import gzip
from io import BytesIO
from proxy.http.parser import HttpParser
from proxy.common.utils import build_http_response
from ontologytimemachine.utils.mock_responses import (
    mock_response_403,
    mock_response_500,
)
from ontologytimemachine.proxy_wrapper import HttpRequestWrapper
from ontologytimemachine.utils.proxy_logic import (
    get_response_from_request,
    do_block_CONNECT_request,
    is_archivo_ontology_request,
    evaluate_configuration,
)
from ontologytimemachine.utils.config import Config, HttpsInterception, parse_arguments
from http.client import responses
import proxy
import sys
from ontologytimemachine.utils.config import (
    HttpsInterception,
    ClientConfigViaProxyAuth,
    parse_arguments
)


default_cfg: Config = Config()
config = default_cfg

IP = default_cfg.host
PORT = default_cfg.port


# config = parse_arguments() # will break pytest discovery in vscode since it 

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# handler = logging.StreamHandler(sys.stdout)
# handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)


class OntologyTimeMachinePlugin(HttpProxyBasePlugin):
    def __init__(self, *args, **kwargs):
        # print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~___________________________OntologyTimeMachinePlugin')
        # logger= logging.getLogger(__name__)
        # logger.debug('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~___________________________debug')
        # logger.info("Config: %s", self.config)
        # handler.setFormatter(formatter)
        # logger.addHandler(handler)
        # print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~___________________________OntologyTimeMachinePlugin')
        logger.info(f"~~~~~~~~~~~___________________________OntologyTimeMachinePlugin Init - Object ID: {id(self)}")
        super().__init__(*args, **kwargs)
        self.config = config
        logger.info(f"Config: {self.config}")

    def before_upstream_connection(self, request: HttpParser) -> HttpParser | None:
        # self.client.config = QUOTE_NONE
        logger.info("Before upstcream connection hook")
        logger.info(f"Request method: {request.method} - Request host: {request.host} - Request path: {request.path} - Request headers: {request.headers}")
        wrapped_request = HttpRequestWrapper(request)
        
        try:
            self.client.request_host = wrapped_request.get_request_host()
        except:
            logger.info('No host')
        
        try:
            self.client.request_path = wrapped_request.get_request_path()
        except:
            logger.info('No path')
                

        if (self.config.clientConfigViaProxyAuth == ClientConfigViaProxyAuth.REQUIRED or self.config.clientConfigViaProxyAuth == ClientConfigViaProxyAuth.OPTIONAL):
            logger.info('Setting up config from auth')
            config_from_auth = evaluate_configuration(wrapped_request, self.config)
            if (not config_from_auth and self.config.clientConfigViaProxyAuth == ClientConfigViaProxyAuth.REQUIRED):
                logger.info( "Client configuration via proxy auth is required btu configuration is not provided, return 500.")
                self.queue_response(mock_response_500)
                return None
            if (not config_from_auth and self.config.clientConfigViaProxyAuth == ClientConfigViaProxyAuth.OPTIONAL):
                logger.info("Auth configuration is optional, not provided.")
            if config_from_auth and not hasattr(self.client, "config"):
                self.client.config = config_from_auth
                logger.info(f"New config: {config_from_auth}")
        if self.config.clientConfigViaProxyAuth == ClientConfigViaProxyAuth.IGNORE:
            logger.info("Ignore auth even if provided")

        # Check if any config was provided via the authentication parameters
        # If so, use that config
        if hasattr(self.client, "config"):
            logger.info("Using the configuration from the Auth")
            config = self.client.config
        else:
            logger.info("Using the proxy configuration")
            config = self.config            
        
        if wrapped_request.is_connect_request():
            logger.info("Handling CONNECT request: configured HTTPS interception mode: %s", config.httpsInterception)
            # Mark if there is a connect request
            if not hasattr(self.client, "mark_connect"):
                self.client.mark_connect = True

            # Check whether to allow CONNECT requests since they can impose a security risk
            if not do_block_CONNECT_request(config):
                logger.info("Allowing the CONNECT request")
                return request
            else:
                logger.info("CONNECT request was blocked due to the configuration")
                return None
    
        if not wrapped_request.is_connect_request():
            logger.info('Skip for the connect request')
            if not wrapped_request.get_request_host():
                if hasattr(self.client, "request_host"):
                    wrapped_request.set_request_host(self.client.request_host)
            if not wrapped_request.get_request_path():
                if hasattr(self.client, "request_path"):
                    wrapped_request.set_request_path(self.client.request_path)
            response = get_response_from_request(wrapped_request, config)
            if response.status_code:
                logger.info('Queue response from proxy logic')
                self.queue_response(response)
                return None

        return request

    def do_intercept(self, _request: HttpParser) -> bool:
        logger.info('Do intercept hook')
        wrapped_request = HttpRequestWrapper(_request)

        # Check if any config was provided via the authentication parameters
        # If so, use that config
        if hasattr(self.client, "config"):
            logger.info("Using the configuration from the Auth")
            config = self.client.config
            logger.info(f'Config: {config}')
        else:
            logger.info("Using the proxy configuration")
            config = self.config

        if config.httpsInterception == HttpsInterception.ALL:
            logger.info("Intercepting all HTTPS requests")
            return True
        elif config.httpsInterception == HttpsInterception.NONE:
            logger.info("Intercepting no HTTPS requests")
            return False
        elif config.httpsInterception == HttpsInterception.BLOCK:
            logger.error("Reached code block for interception decision in block mode which should have been blocked before")
            # this should actually be not triggered as the CONNECT request should have been blocked before
            return False
        elif config.httpsInterception == HttpsInterception.ARCHIVO:
            if not wrapped_request.get_request_host():
                if hasattr(self.client, "request_host"):
                    wrapped_request.set_request_host(self.client.request_host)
            if not wrapped_request.get_request_path():
                if hasattr(self.client, "request_path"):
                    wrapped_request.set_request_path(self.client.request_path)
            try:
                if is_archivo_ontology_request(wrapped_request):
                    logger.info("Intercepting HTTPS request since it is an Archivo ontology request")
                    return True
            except Exception as e:
                logger.error("Error while checking if request is an Archivo ontology request: %s", e, exc_info=True)
            logger.info("No Interception of HTTPS request since it is NOT an Archivo ontology request")
            return False
        else:
            logger.info("Unknown Option for httpsInterception: %s -> fallback to no interception", self.config.httpsInterception,)
            return False

    def handle_client_request(self, request: HttpParser) -> HttpParser:
        logger.info("Handle client request hook")
        logger.info(f"Request method: {request.method} - Request host: {request.host} - Request path: {request.path} - Request headers: {request.headers}")

        wrapped_request = HttpRequestWrapper(request)
        if (wrapped_request.is_head_request() or wrapped_request.is_get_request()) and hasattr(self.client, "mark_connect"):
            logger.info('HEAD or GET and has mark_connect')
            if self.client.mark_connect:
                if hasattr(self.client, "config"):
                    logger.info("Using the configuration from the Auth")
                    config = self.client.config
                else:
                    logger.info("Using the proxy configuration")
                    config = self.config  
                if not wrapped_request.get_request_host():
                    if hasattr(self.client, "request_host"):
                        wrapped_request.set_request_host(self.client.request_host)
                if not wrapped_request.get_request_path():
                    if hasattr(self.client, "request_path"):
                        wrapped_request.set_request_path(self.client.request_path)

                response = get_response_from_request(wrapped_request, config)
            if response and response.status_code:
                logger.info(response.status_code)
                self.queue_response(response)
                return None

        logger.info('Return original request')
        return request

    def handle_upstream_chunk(self, chunk: memoryview):
        return chunk

    def queue_response(self, response):
        self.client.queue(
            build_http_response(
                response.status_code,
                reason=bytes(responses[response.status_code], "utf-8"),
                headers={
                    bytes(key, "utf-8"): bytes(value, "utf-8") for key, value in response.headers.items()
                },
                body=response.content,
            )
        )


if __name__ == "__main__":

    config = parse_arguments()
    from ontologytimemachine.utils.config import logger

    sys.argv = [sys.argv[0]]

    # check it https interception is enabled add the necessary certificates to proxypy
    if config.httpsInterception != (HttpsInterception.NONE or HttpsInterception.BLOCK):
        sys.argv += [
            "--ca-key-file", "ca-key.pem",
            "--ca-cert-file", "ca-cert.pem",
            "--ca-signing-key-file", "ca-signing-key.pem",
        ]
    
    for host in config.host:
        sys.argv += [
            "--hostname", host,
        ]

    sys.argv += [
        "--port", str(config.port),
        # "--log-level", config.logLevel.name,
        '--insecure-tls-interception',  # without it the proxy would not let through a response using an invalid upstream certificate in interception mode
                                        # since there currently is a bug in proxypy when a connect request uses an IP address instead of a domain name
                                        # the proxy would not be able to work corectly in transparent mode using 3proxy setup since it tries to match
                                        # the IP address as hostname with the certificate instead of the domain name in the SNI field
        "--plugins", __name__ + ".OntologyTimeMachinePlugin",
    ]

    logger.info("Starting OntologyTimeMachineProxy server...")
    logger.debug("starting proxypy engine with arguments: %s", sys.argv)
    proxy.main()
