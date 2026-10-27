class AppError(Exception):
    status_code = 400
    code = 40000


class JobAlreadyRunning(AppError):
    status_code = 409
    code = 40901
