FROM ubuntu:focal AS builder
    ARG CMAKE_OPTIONS

    # Avoid interactive installation
    ENV DEBIAN_FRONTEND=noninteractive 
    RUN apt-get update
    RUN apt-get -y install wget build-essential cmake git pkg-config

    WORKDIR /src

    # Create a user and set up workspace
    RUN groupadd -g 1000 devuser && \
        useradd -m -u 1000 -g devuser devuser

    COPY .devcontainer/install-deps.sh .
    RUN chmod +x install-deps.sh
    RUN ./install-deps.sh -d

    COPY ../ .
    RUN rm -rf build \
        && mkdir build \
        && cd build \
        && cmake .. -DBUILD_SLOG_TESTS=OFF ${CMAKE_OPTIONS} -DCMAKE_BUILD_TYPE=release \
        && make -j$(nproc) \
        && cd ..

    USER devuser

FROM ubuntu:focal AS runner
    # If set (to anything), also create an image with tools (exclude the toolings)
    ARG INCLUDE_TOOLS

    # Recreate user devuser in the runner stage
    RUN groupadd -g 1000 devuser && \
        useradd -m -u 1000 -g devuser devuser

    WORKDIR /opt/slog
    COPY --from=builder /src/build/janus .
    COPY --from=builder /src/build/slog .
    COPY --from=builder /src/build/client .
    COPY --from=builder /src/build/benchmark .
    COPY --from=builder /src/build/scheduler_benchmark .
    COPY --from=builder /src/examples/* ./
    COPY --from=builder /src/tools/ tools/

    ENV DEBIAN_FRONTEND=noninteractive
    RUN apt-get update && apt-get install -y \
        wget curl git netcat cmake build-essential pkg-config sudo

    RUN if [ -n "$INCLUDE_TOOLS" ]; then \
        apt-get update; \
        apt-get -y install python3 python3-pip; \
        python3 -m pip install -r tools/requirements.txt; \
        chmod +x tools/*.py; \
        fi

    RUN echo 'devuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
    USER devuser

    ENV PATH="/opt/slog:${PATH}"
    ENV PATH="/opt/slog/tools:${PATH}"
