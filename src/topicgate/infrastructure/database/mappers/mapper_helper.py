class MapperHelper:
    @staticmethod
    def optional_int(value: object, field_name: str) -> int | None:
        if value is None:
            return None
        return MapperHelper.required_int(value, field_name)

    @staticmethod
    def required_int(value: object, field_name: str) -> int:
        if type(value) is not int:
            raise ValueError(f"MQTT configuration {field_name} must be an integer.")
        return value

    @staticmethod
    def required_str(value: object, field_name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"MQTT configuration {field_name} must be a string.")
        return value

    @staticmethod
    def required_bool(value: object, field_name: str) -> bool:
        if type(value) is not bool:
            raise ValueError(f"MQTT configuration {field_name} must be a boolean.")
        return value
