FROM curlimages/curl:latest

USER root
COPY entrypoint.sh /entrypoint
RUN chmod 555 /entrypoint

USER curl_user
ENTRYPOINT /entrypoint
