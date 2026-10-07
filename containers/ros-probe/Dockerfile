FROM docker.io/library/ros@sha256:5d8bdefcfb553802cca2fff87233f0c0adfbbd50e87e7c64c9af9a098250e6b1

LABEL io.d1env.project="d1env" \
      io.d1env.source="d1env/ros-probe" \
      io.d1env.kind="ros-probe" \
      org.opencontainers.image.description="D1Env CPU ROS communication software probe; no robot interface"

# All ROS/Python dependencies are inherited from the pinned official base. No apt/pip additions.
COPY --chmod=0555 probe.py read_status.py entrypoint.sh /opt/d1env/
ENV HOME=/tmp \
    ROS_LOG_DIR=/tmp/roslogs \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001:10001
ENTRYPOINT ["/opt/d1env/entrypoint.sh"]
CMD ["idle"]
