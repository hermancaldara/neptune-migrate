from aws_requests_auth.aws_auth import AWSRequestsAuth


def get_aws_auth(config):
    return AWSRequestsAuth(
        aws_access_key=config.get("aws_access_key"),
        aws_secret_access_key=config.get("aws_secret_access_key"),
        aws_host=config.get("aws_neptune_host"),
        aws_region=config.get("aws_region"),
        aws_service="neptune-db",
    )
