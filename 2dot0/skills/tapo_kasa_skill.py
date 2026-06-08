import os
import asyncio
from typing import Optional

from pydantic import BaseModel, Field
from skills.base_skill import BaseSkill


class TapoKasaInput(BaseModel):
    target_device: str = Field(
        description=(
            "The name or alias of the specific light/plug to control (e.g., 'Desk Lamp', 'Living Room'). "
            "Can also be an IP address."
        )
    )
    action: str = Field(
        description="The action to perform. Must be one of: 'on', 'off', 'status', or 'set_brightness'."
    )
    brightness: Optional[int] = Field(
        default=None,
        description="The brightness level (1-100) to set if the action is 'set_brightness'."
    )


class TapoKasaSkill(BaseSkill):
    name = "control_tapo_kasa_devices"
    description = (
        "Controls TP-Link Tapo or Kasa smart lights and plugs on the local network. "
        "Use this to turn devices on or off, check their current status, or adjust brightness."
    )
    input_model = TapoKasaInput

    def execute(self, params: TapoKasaInput) -> str:
        """
        BaseSkill expects a synchronous method, but python-kasa relies on asyncio.
        We bridge this by spinning up an event loop for the execution.
        """
        try:
            return asyncio.run(self._run_command(params))
        except Exception as exc:
            return f"Error interacting with Tapo/Kasa devices: {exc}"

    async def _run_command(self, params: TapoKasaInput) -> str:
        try:
            from kasa import Discover, SmartDeviceException
        except ImportError:
            return "Error: The 'python-kasa' library is missing. Run 'pip install python-kasa'."

        # Grab credentials from the environment
        tapo_user = os.getenv("TAPO_USERNAME")
        tapo_pass = os.getenv("TAPO_PASSWORD")
        
        credentials = None
        if tapo_user and tapo_pass:
            credentials = (tapo_user, tapo_pass)

        # 1. Discover devices using authentication
        try:
            found_devices = await Discover.discover(credentials=credentials)
        except Exception as e:
            return f"Discovery failed (check credentials): {e}"
        
        if not found_devices:
            return "No Tapo or Kasa devices were found on the local network."

        # 2. Find the target device
        target = None
        for ip, device in found_devices.items():
            try:
                await device.update()
            except SmartDeviceException:
                # Skip devices that fail to update (e.g., offline or auth failed for that specific IP)
                continue
                
            if params.target_device.lower() in device.alias.lower() or params.target_device == ip:
                target = device
                break

        if not target:
            available_aliases = [d.alias for d in found_devices.values() if d.alias]
            return (
                f"Device '{params.target_device}' not found or authentication failed. "
                f"Available devices on the network: {', '.join(available_aliases)}."
            )

        # 3. Execute the requested action
        action = params.action.lower()
        try:
            if action == "status":
                state = "ON" if target.is_on else "OFF"
                brightness_info = f", Brightness: {target.brightness}%" if target.is_dimmable else ""
                return f"Status of '{target.alias}': {state}{brightness_info}"

            elif action == "on":
                await target.turn_on()
                return f"Successfully turned ON '{target.alias}'."

            elif action == "off":
                await target.turn_off()
                return f"Successfully turned OFF '{target.alias}'."

            elif action == "set_brightness":
                if not target.is_dimmable:
                    return f"Device '{target.alias}' does not support brightness adjustments."
                if params.brightness is None or not (1 <= params.brightness <= 100):
                    return "Error: Please provide a valid brightness value between 1 and 100."

                await target.set_brightness(params.brightness)
                return f"Successfully set '{target.alias}' brightness to {params.brightness}%."

            else:
                return f"Unknown action: '{action}'."

        except SmartDeviceException as e:
            return f"Failed to execute '{action}' on '{target.alias}': {e}"