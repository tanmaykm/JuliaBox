# Docker file for JuliaAPIBox
# Version:27

FROM tanmaykm/juliabox:27

MAINTAINER Tanmay Mohapatra

ADD setup_julia.sh /tmp/setup_julia.sh

RUN mkdir /home/juser/.juliabox

RUN /tmp/setup_julia.sh

ENTRYPOINT julia -e 'using JuliaBox; process()'
