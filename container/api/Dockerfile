# Docker file for JuliaBox APIs
# Version:42

FROM julialang/juliaboxpkgdist:v0.3.12

MAINTAINER Tanmay Mohapatra

RUN ln -fs /opt/julia/bin/julia /usr/bin/julia

# add juser
# create group and user with specific ids if required on systems where the user running juliabox is not the first user
RUN groupadd juser \
    && useradd -m -d /home/juser -s /bin/bash -g juser -G staff juser \
    && echo "export HOME=/home/juser" >> /home/juser/.bashrc

# link Julia v0.3
RUN ln -fs /opt/julia_0.3.12 /opt/julia-0.3.12 && \
    ln -fs /opt/julia-0.3.12 /opt/julia-0.3

# add Julia v0.4 build
RUN mkdir -p /opt/julia-0.4.5 && \
    curl -s -L https://julialang.s3.amazonaws.com/bin/linux/x64/0.4/julia-0.4.5-linux-x86_64.tar.gz | tar -C /opt/julia-0.4.5 -x -z --strip-components=1 -f -
RUN ln -fs /opt/julia-0.4.5 /opt/julia-0.4

# add Julia v0.5 nightly build
RUN mkdir -p /opt/julia-0.5.0-dev && \
    curl -s -L https://status.julialang.org/download/linux-x86_64 | tar -C /opt/julia-0.5.0-dev -x -z --strip-components=1 -f -
RUN ln -fs /opt/julia-0.5.0-dev /opt/julia-0.5

# Make Julia 0.4 the default
RUN rm /opt/julia && ln -fs /opt/julia-0.4.5 /opt/julia

# Install CUDA
LABEL com.nvidia.volumes.needed="nvidia_driver"

ENV NVIDIA_GPGKEY_SUM bd841d59a27a406e513db7d405550894188a4c1cd96bf8aa4f82f1b39e0b5c1c
ENV NVIDIA_GPGKEY_FPR 889bee522da690103c4b085ed88c3d385c37d3be

RUN apt-key adv --fetch-keys http://developer.download.nvidia.com/compute/cuda/repos/GPGKEY && \
    apt-key adv --export --no-emit-version -a $NVIDIA_GPGKEY_FPR | tail -n +2 > cudasign.pub && \
    echo "$NVIDIA_GPGKEY_SUM  cudasign.pub" | sha256sum -c --strict - && rm cudasign.pub && \
    echo "deb http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1404/x86_64 /" > /etc/apt/sources.list.d/cuda.list

ENV CUDA_VERSION 7.5
LABEL com.nvidia.cuda.version="7.5"

ENV CUDA_PKG_VERSION 7-5=7.5-18
RUN apt-get update && apt-get install -y --no-install-recommends --force-yes \
        cuda-nvrtc-$CUDA_PKG_VERSION \
        cuda-cusolver-$CUDA_PKG_VERSION \
        cuda-cublas-$CUDA_PKG_VERSION \
        cuda-cufft-$CUDA_PKG_VERSION \
        cuda-curand-$CUDA_PKG_VERSION \
        cuda-cusparse-$CUDA_PKG_VERSION \
        cuda-npp-$CUDA_PKG_VERSION \
        cuda-cudart-$CUDA_PKG_VERSION && \
    ln -s cuda-$CUDA_VERSION /usr/local/cuda && \
    rm -rf /var/lib/apt/lists/*

RUN wget -O /tmp/cuda.run http://developer.download.nvidia.com/compute/cuda/7.5/Prod/local_installers/cuda_7.5.18_linux.run && \
    sh /tmp/cuda.run --silent --toolkit && \
    rm -f /tmp/cuda.run

RUN echo "/usr/local/cuda/lib" >> /etc/ld.so.conf.d/cuda.conf && \
    echo "/usr/local/cuda/lib64" >> /etc/ld.so.conf.d/cuda.conf && \
    echo "/usr/local/cuda/nvvm/lib64" >> /etc/ld.so.conf.d/cuda.conf && \
    ldconfig

RUN echo "/usr/local/nvidia/lib" >> /etc/ld.so.conf.d/nvidia.conf && \
    echo "/usr/local/nvidia/lib64" >> /etc/ld.so.conf.d/nvidia.conf

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib:/usr/local/cuda/lib64:/usr/local/cuda/nvvm/lib64
ENV PATH=/usr/local/nvidia/bin:/usr/local/cuda/bin:/usr/local/texlive/2014/bin/x86_64-linux:/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin:/opt/julia/bin

# Install ArrayFire
RUN wget -O /tmp/af.sh http://ci.arrayfire.org/userContent/Linux/ArrayFire-no-gl-v3.3.2_Linux_x86_64.sh && \
    sh /tmp/af.sh --skip-license --prefix=/usr/local && \
    rm -f /tmp/af.sh

USER juser
ENV HOME /home/juser
ENV PATH /usr/local/nvidia/bin:/usr/local/cuda/bin:/usr/local/texlive/2014/bin/x86_64-linux:/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin:/opt/julia/bin
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib:/usr/local/cuda/lib64:/usr/local/cuda/nvvm/lib64
WORKDIR /home/juser

RUN /opt/julia-0.3/bin/julia  -e "try; Pkg.installed(\"JuliaWebAPI\"); catch; Pkg.clone(\"https://github.com/tanmaykm/JuliaWebAPI.jl\"); end"
RUN /opt/julia-0.4/bin/julia  -e "try; Pkg.installed(\"JuliaWebAPI\"); catch; Pkg.clone(\"https://github.com/tanmaykm/JuliaWebAPI.jl\"); end"
RUN /opt/julia-0.5/bin/julia  -e "try; Pkg.installed(\"JuliaWebAPI\"); catch; Pkg.clone(\"https://github.com/tanmaykm/JuliaWebAPI.jl\"); end"

ENTRYPOINT ["julia", "-e", "using JuliaWebAPI; using Compat; process();"]
