from datetime import datetime

import timesetter

wanted_system_time = datetime(year=1997, month=7, day=29, hour=0, minute=0, second=0)

timesetter.set(wanted_system_time)
