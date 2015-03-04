{
    "port" : 8888,
    "async_job_ports" : (8889,8890),
    # debug:10, info:20, warning:30, error:40
    "jbox_log_level": 10,
    "root_log_level": 40,

    # Number of active containers to allow per instance
    "numlocalmax" : $$NUM_LOCALMAX,

    # Installation specific session key. Used for encryption and signing. 
    "sesskey" : "$$SESSKEY",

    # Maximum memory allowed per docker container.
    # To be able to use `mem_limit`, the host kernel must be configured to support the same. 
    # See <http://docs.docker.io/en/latest/installation/kernel/#memory-and-swap-accounting-on-debian-ubuntu> 
    # Default 1GB containers. multiplier can be applied from user profile
    "mem_limit" : 1000000000,
    # Max 1024 cpu slices. default maximum allowed is 1/8th of total cpu slices. multiplier can be applied from user profile.
    "cpu_limit" : 128,

    # The docker image to launch
    "docker_image" : "$$DOCKER_IMAGE",

    "cloud_host": {
    	"install_id": "JuliaApiBox",
    	"region": "us-east-1",

    	# Enable/disable features
    	"s3": False,
    	"dynamodb": True,
    	"cloudwatch": True,
    	"autoscale": True,
    	"route53": True,
    	"ebs": False,
        "ses": False,

    	"autoscale_group": "juliaapibox",
    	"route53_domain": "juliabox.org",

        # Average cluster load at which to initiate scale up
    	"scale_up_at_load": 70,
    	"scale_up_policy": "addinstance",
        # Self teminate if required to scale down
        "scale_down" : False,

    	"dummy" : "dummy"
    },

    "dummy" : "dummy"
}

