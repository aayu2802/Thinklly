"""
Teacher Form Validation Utilities
Provides comprehensive validation for teacher data entry
"""

import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class TeacherValidator:
    """Validates teacher form data"""
    
    @staticmethod
    def validate_phone(phone, field_name="Phone"):
        """
        Validate phone number - must be exactly 10 digits
        Args:
            phone: Phone number string
            field_name: Name of the field for error messages
        Returns:
            Cleaned phone number (digits only)
        Raises:
            ValidationError if invalid
        """
        if not phone:
            return None  # Optional field
            
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\+]', '', phone.strip())
        
        # Check if only digits remain
        if not cleaned.isdigit():
            raise ValidationError(field_name, "must contain only digits")
        
        # Check length
        if len(cleaned) != 10:
            raise ValidationError(field_name, "must be exactly 10 digits")
        
        return cleaned
    
    @staticmethod
    def validate_pincode(pincode):
        """
        Validate Indian pincode - must be exactly 6 digits
        Args:
            pincode: Pincode string
        Returns:
            Cleaned pincode (digits only)
        Raises:
            ValidationError if invalid
        """
        if not pincode:
            return None  # Optional field
            
        cleaned = pincode.strip()
        
        # Check if only digits
        if not cleaned.isdigit():
            raise ValidationError("Pincode", "must contain only digits")
        
        # Check length
        if len(cleaned) != 6:
            raise ValidationError("Pincode", "must be exactly 6 digits")
        
        return cleaned
    
    @staticmethod
    def validate_email(email):
        """
        Validate email format
        Args:
            email: Email string
        Returns:
            Cleaned email (lowercase)
        Raises:
            ValidationError if invalid
        """
        if not email:
            raise ValidationError("Email", "is required")
        
        email = email.strip().lower()
        
        # Basic email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("Email", "is not a valid email address")
        
        return email
    
    @staticmethod
    def validate_date_of_birth(dob_str, min_age=18, max_age=70):
        """
        Validate date of birth
        Args:
            dob_str: Date string in YYYY-MM-DD format
            min_age: Minimum age allowed (default 18)
            max_age: Maximum age allowed (default 70)
        Returns:
            date object
        Raises:
            ValidationError if invalid
        """
        if not dob_str:
            raise ValidationError("Date of Birth", "is required")
        
        try:
            dob = datetime.strptime(dob_str.strip(), '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError("Date of Birth", "must be in YYYY-MM-DD format")
        
        # Check if date is in the future
        if dob >= date.today():
            raise ValidationError("Date of Birth", "cannot be in the future")
        
        # Calculate age
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
        if age < min_age:
            raise ValidationError("Date of Birth", f"teacher must be at least {min_age} years old")
        
        if age > max_age:
            raise ValidationError("Date of Birth", f"teacher cannot be more than {max_age} years old")
        
        return dob
    
    @staticmethod
    def validate_joining_date(joining_date_str, dob):
        """
        Validate joining date - must be at least 18 years after DOB
        Args:
            joining_date_str: Joining date string in YYYY-MM-DD format
            dob: Date of birth (date object)
        Returns:
            date object
        Raises:
            ValidationError if invalid
        """
        if not joining_date_str:
            raise ValidationError("Joining Date", "is required")
        
        try:
            joining_date = datetime.strptime(joining_date_str.strip(), '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError("Joining Date", "must be in YYYY-MM-DD format")
        
        # Check if joining date is in the future (more than 1 month ahead)
        today = date.today()
        max_future_date = today + relativedelta(months=1)
        if joining_date > max_future_date:
            raise ValidationError("Joining Date", "cannot be more than 1 month in the future")
        
        # Calculate minimum joining date (DOB + 18 years)
        min_joining_date = dob + relativedelta(years=18)
        
        if joining_date < min_joining_date:
            raise ValidationError(
                "Joining Date",
                f"must be at least 18 years after date of birth (minimum: {min_joining_date.strftime('%Y-%m-%d')})"
            )
        
        return joining_date
    
    @staticmethod
    def validate_employee_id(employee_id):
        """
        Validate employee ID - must be alphanumeric, 3-50 characters
        Args:
            employee_id: Employee ID string
        Returns:
            Cleaned employee ID
        Raises:
            ValidationError if invalid
        """
        if not employee_id:
            raise ValidationError("Employee ID", "is required")
        
        cleaned = employee_id.strip()
        
        # Check length
        if len(cleaned) < 3:
            raise ValidationError("Employee ID", "must be at least 3 characters")
        
        if len(cleaned) > 50:
            raise ValidationError("Employee ID", "must not exceed 50 characters")
        
        # Check if alphanumeric (allow hyphens and underscores)
        if not re.match(r'^[a-zA-Z0-9_-]+$', cleaned):
            raise ValidationError("Employee ID", "must contain only letters, numbers, hyphens, and underscores")
        
        return cleaned
    
    @staticmethod
    def validate_name(name, field_name="Name", min_length=2, max_length=100):
        """
        Validate name fields
        Args:
            name: Name string
            field_name: Name of the field for error messages
            min_length: Minimum length
            max_length: Maximum length
        Returns:
            Cleaned name (title case)
        Raises:
            ValidationError if invalid
        """
        if not name:
            raise ValidationError(field_name, "is required")
        
        cleaned = name.strip()
        
        if len(cleaned) < min_length:
            raise ValidationError(field_name, f"must be at least {min_length} characters")
        
        if len(cleaned) > max_length:
            raise ValidationError(field_name, f"must not exceed {max_length} characters")
        
        # Allow letters, spaces, hyphens, apostrophes
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", cleaned):
            raise ValidationError(field_name, "must contain only letters, spaces, hyphens, and apostrophes")
        
        return cleaned.title()
    
    @staticmethod
    def validate_all_teacher_data(form_data):
        """
        Validate all teacher form data at once
        Args:
            form_data: Dictionary of form data
        Returns:
            Dictionary of validated and cleaned data
        Raises:
            ValidationError on first validation failure
        """
        validated = {}
        
        # Employee ID
        validated['employee_id'] = TeacherValidator.validate_employee_id(
            form_data.get('employee_id')
        )
        
        # Names
        validated['first_name'] = TeacherValidator.validate_name(
            form_data.get('first_name'), 'First Name'
        )
        validated['last_name'] = TeacherValidator.validate_name(
            form_data.get('last_name'), 'Last Name'
        )
        
        # Middle name is optional
        middle_name = form_data.get('middle_name', '').strip()
        if middle_name:
            validated['middle_name'] = TeacherValidator.validate_name(
                middle_name, 'Middle Name'
            )
        else:
            validated['middle_name'] = None
        
        # Email
        validated['email'] = TeacherValidator.validate_email(
            form_data.get('email')
        )
        
        # Phone numbers
        validated['phone_primary'] = TeacherValidator.validate_phone(
            form_data.get('phone_primary'), 'Primary Phone'
        )
        
        phone_alternate = form_data.get('phone_alternate', '').strip()
        if phone_alternate:
            validated['phone_alternate'] = TeacherValidator.validate_phone(
                phone_alternate, 'Alternate Phone'
            )
        else:
            validated['phone_alternate'] = None
        
        # Emergency contact
        emergency_phone = form_data.get('emergency_contact_number', '').strip()
        if emergency_phone:
            validated['emergency_contact_number'] = TeacherValidator.validate_phone(
                emergency_phone, 'Emergency Contact Number'
            )
        else:
            validated['emergency_contact_number'] = None
        
        # Pincode
        pincode = form_data.get('address_pincode', '').strip()
        if pincode:
            validated['address_pincode'] = TeacherValidator.validate_pincode(pincode)
        else:
            validated['address_pincode'] = None
        
        # Date of Birth
        validated['date_of_birth'] = TeacherValidator.validate_date_of_birth(
            form_data.get('date_of_birth')
        )
        
        # Joining Date (must be after DOB + 18 years)
        validated['joining_date'] = TeacherValidator.validate_joining_date(
            form_data.get('joining_date'),
            validated['date_of_birth']
        )
        
        # Gender
        gender = form_data.get('gender', '').strip()
        if gender not in ['Male', 'Female', 'Other']:
            raise ValidationError("Gender", "must be Male, Female, or Other")
        validated['gender'] = gender
        
        # Employee Status
        status = form_data.get('employee_status', 'Active')
        if status not in ['Active', 'Inactive', 'On Leave', 'Resigned']:
            status = 'Active'
        validated['employee_status'] = status
        
        # Optional address fields (no validation needed, just clean)
        validated['address_street'] = form_data.get('address_street', '').strip() or None
        validated['address_city'] = form_data.get('address_city', '').strip() or None
        validated['address_state'] = form_data.get('address_state', '').strip() or None
        validated['emergency_contact_name'] = form_data.get('emergency_contact_name', '').strip() or None
        
        return validated


def format_validation_error(error):
    """
    Format ValidationError for user-friendly display
    Args:
        error: ValidationError instance
    Returns:
        Formatted error message string
    """
    return f"{error.field} {error.message}"
