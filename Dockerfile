FROM sport-base:v1
RUN rm -rf /participant
COPY participant /participant
RUN chmod +x /participant/run_all.sh
WORKDIR /participant
ENTRYPOINT ["/participant/run_all.sh"]
